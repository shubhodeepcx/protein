"""Recorded-HTTP tests for the three external database clients.

Every upstream call is mocked with respx against fixtures in tests/fixtures/.
Nothing in this file may reach the network.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.services.alphafold import AlphaFoldClient
from app.services.external import SourceNotFoundError, SourceUnavailableError
from app.services.rcsb import RCSBClient
from app.services.uniprot import UniProtClient
from tests.helpers import load_bytes, load_json

RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_ENTRY = "https://data.rcsb.org/rest/v1/core/entry/"
RCSB_ENTITY = "https://data.rcsb.org/rest/v1/core/polymer_entity/"
RCSB_FILES = "https://files.rcsb.org/download/"
AF_PREDICTION = "https://alphafold.ebi.ac.uk/api/prediction/"
AF_FILES = "https://alphafold.ebi.ac.uk/files/"
UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_ENTRY_P01308 = "https://rest.uniprot.org/uniprotkb/P01308.json"


def _mock_rcsb_data_api() -> tuple[respx.Route, respx.Route]:
    entry = respx.get(url__startswith=RCSB_ENTRY).mock(
        return_value=httpx.Response(200, json=load_json("rcsb_entry_1CRN.json"))
    )
    entity = respx.get(url__startswith=RCSB_ENTITY).mock(
        return_value=httpx.Response(200, json=load_json("rcsb_polymer_entity_1CRN_1.json"))
    )
    return entry, entity


# --------------------------------------------------------------------- RCSB


@respx.mock
async def test_rcsb_search_enriches_each_hit_with_entry_metadata() -> None:
    search = respx.post(RCSB_SEARCH).mock(
        return_value=httpx.Response(200, json=load_json("rcsb_search_insulin.json"))
    )
    _mock_rcsb_data_api()

    results = await RCSBClient().search("insulin")

    assert search.called
    body = search.calls.last.request.content.decode()
    assert "full_text" in body and "insulin" in body

    assert [r.source_id for r in results] == ["1BOM", "2FHW"]
    first = results[0]
    assert first.source == "rcsb"
    assert first.title is not None and "CRAMBIN" in first.title.upper()
    assert first.organism == "Crambe hispanica subsp. abyssinica"
    assert first.resolution == pytest.approx(1.5)
    assert first.method == "X-ray"
    assert first.release_year == 1981
    assert first.sequence_length == 46


@respx.mock
async def test_rcsb_search_keeps_hit_when_enrichment_fails() -> None:
    respx.post(RCSB_SEARCH).mock(
        return_value=httpx.Response(200, json=load_json("rcsb_search_insulin.json"))
    )
    respx.get(url__startswith=RCSB_ENTRY).mock(return_value=httpx.Response(500))

    results = await RCSBClient().search("insulin")

    # A broken Data API degrades the card, it does not sink the source.
    assert [r.source_id for r in results] == ["1BOM", "2FHW"]
    assert all(r.title is None for r in results)


@respx.mock
async def test_rcsb_search_handles_no_content() -> None:
    respx.post(RCSB_SEARCH).mock(return_value=httpx.Response(204))
    assert await RCSBClient().search("zzzzz") == []


@respx.mock
async def test_rcsb_fetch_metadata_normalises_and_caches() -> None:
    entry, entity = _mock_rcsb_data_api()
    client = RCSBClient()

    meta = await client.fetch_metadata("1crn")
    assert meta["source"] == "rcsb"
    assert meta["source_id"] == "1CRN"
    assert meta["organism"] == "Crambe hispanica subsp. abyssinica"
    assert meta["resolution"] == pytest.approx(1.5)
    assert meta["release_year"] == 1981
    assert meta["file_url"] == "https://files.rcsb.org/download/1CRN.cif"

    # Second lookup is served from the TTL cache — no extra upstream calls.
    await client.fetch_metadata("1CRN")
    assert entry.call_count == 1
    assert entity.call_count == 1


@respx.mock
async def test_rcsb_fetch_metadata_missing_entry_raises_not_found() -> None:
    respx.get(url__startswith=RCSB_ENTRY).mock(return_value=httpx.Response(404))
    with pytest.raises(SourceNotFoundError):
        await RCSBClient().fetch_metadata("9ZZZ")


async def test_rcsb_rejects_malformed_id_without_any_http() -> None:
    with pytest.raises(SourceNotFoundError):
        await RCSBClient().fetch_metadata("not-a-pdb-id")


@respx.mock
async def test_rcsb_download_structure_returns_cif() -> None:
    cif = load_bytes("1CRN.cif")
    route = respx.get(f"{RCSB_FILES}1CRN.cif").mock(return_value=httpx.Response(200, content=cif))

    content, fmt = await RCSBClient().download_structure("1crn")

    assert route.called
    assert fmt == "cif"
    assert content.startswith(b"data_1CRN")


@respx.mock
async def test_rcsb_download_structure_404_raises_not_found() -> None:
    respx.get(url__startswith=RCSB_FILES).mock(return_value=httpx.Response(404))
    with pytest.raises(SourceNotFoundError):
        await RCSBClient().download_structure("9ZZZ")


@respx.mock
async def test_rcsb_search_upstream_error_raises_unavailable() -> None:
    respx.post(RCSB_SEARCH).mock(return_value=httpx.Response(503))
    with pytest.raises(SourceUnavailableError):
        await RCSBClient().search("insulin")


# ---------------------------------------------------------------- AlphaFold


def _prediction_with_stale_pdb_url() -> list[dict]:
    """P69905 fixture whose `pdbUrl` is one version behind `latestVersion` (6).

    Gives the authoritative leg and the version-derived fallback leg genuinely
    different URLs, so tests can still exercise two distinct download
    attempts even though the fixture's `pdbUrl` and `latestVersion` normally
    agree.
    """
    prediction = load_json("alphafold_prediction_P69905.json")
    prediction[0]["pdbUrl"] = f"{AF_FILES}AF-P69905-F1-model_v5.pdb"
    return prediction


@respx.mock
async def test_alphafold_search_resolves_through_uniprot_crossrefs() -> None:
    route = respx.get(url__startswith=UNIPROT_SEARCH).mock(
        return_value=httpx.Response(200, json=load_json("uniprot_search_insulin.json"))
    )

    results = await AlphaFoldClient().search("insulin")

    # AlphaFold DB has no full-text endpoint: the query goes to UniProtKB with
    # UniProt's own AlphaFoldDB cross-reference filter applied.
    assert route.called
    query = route.calls.last.request.url.params["query"]
    assert "insulin" in query
    assert "database:alphafolddb" in query

    assert [r.source_id for r in results] == ["P01308", "P06213"]
    assert all(r.source == "alphafold" for r in results)
    assert results[0].title == "Insulin"
    assert results[0].organism == "Homo sapiens"
    assert results[0].description is not None
    assert results[0].sequence_length == 110
    assert results[0].method == "AlphaFold prediction"


@respx.mock
async def test_alphafold_fetch_metadata_normalises_prediction() -> None:
    route = respx.get(f"{AF_PREDICTION}P69905").mock(
        return_value=httpx.Response(200, json=load_json("alphafold_prediction_P69905.json"))
    )
    client = AlphaFoldClient()

    meta = await client.fetch_metadata("p69905")
    assert meta["source"] == "alphafold"
    assert meta["source_id"] == "P69905"
    assert meta["title"] == "Hemoglobin subunit alpha"
    assert meta["organism"] == "Homo sapiens"
    assert meta["confidence"] == pytest.approx(98.06)
    assert meta["sequence_length"] == 142
    assert meta["release_year"] == 2025
    assert meta["pdb_url"].endswith("AF-P69905-F1-model_v6.pdb")

    await client.fetch_metadata("P69905")
    assert route.call_count == 1


@respx.mock
async def test_alphafold_fetch_metadata_404_raises_not_found() -> None:
    respx.get(url__startswith=AF_PREDICTION).mock(return_value=httpx.Response(404, json={}))
    with pytest.raises(SourceNotFoundError):
        await AlphaFoldClient().fetch_metadata("Q0Q0Q0")


@respx.mock
async def test_alphafold_empty_prediction_list_raises_not_found() -> None:
    respx.get(url__startswith=AF_PREDICTION).mock(return_value=httpx.Response(200, json=[]))
    with pytest.raises(SourceNotFoundError):
        await AlphaFoldClient().fetch_metadata("Q0Q0Q0")


@respx.mock
async def test_alphafold_download_structure_uses_pdb_url() -> None:
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=load_json("alphafold_prediction_P69905.json"))
    )
    route = respx.get(f"{AF_FILES}AF-P69905-F1-model_v6.pdb").mock(
        return_value=httpx.Response(200, content=b"HEADER    TEST\nEND\n")
    )

    content, fmt = await AlphaFoldClient().download_structure("P69905")

    assert route.called
    assert fmt == "pdb"
    assert content.startswith(b"HEADER")


@respx.mock
async def test_alphafold_download_5xx_then_404_fallback_is_unavailable_not_missing() -> None:
    """A 5xx anywhere in the chain must never be reported as 'no model'.

    The live pdbUrl is down (503) and the version-derived fallback 404s.
    Classifying on the last attempt alone would tell the user the structure
    does not exist.
    """
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=_prediction_with_stale_pdb_url())
    )
    respx.get(f"{AF_FILES}AF-P69905-F1-model_v5.pdb").mock(return_value=httpx.Response(503))
    respx.get(f"{AF_FILES}AF-P69905-F1-model_v6.pdb").mock(return_value=httpx.Response(404))

    with pytest.raises(SourceUnavailableError) as excinfo:
        await AlphaFoldClient().download_structure("P69905")
    assert "503" in str(excinfo.value)


@respx.mock
async def test_alphafold_download_404_on_published_url_is_not_found() -> None:
    """A 404 on the URL AlphaFold itself published really is a missing file."""
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=load_json("alphafold_prediction_P69905.json"))
    )
    respx.get(url__startswith=AF_FILES).mock(return_value=httpx.Response(404))

    with pytest.raises(SourceNotFoundError):
        await AlphaFoldClient().download_structure("P69905")


@respx.mock
async def test_alphafold_download_404_on_obsolete_fallback_only_is_unavailable() -> None:
    """Without a published pdbUrl the version-derived guess 404ing says nothing about the model."""
    prediction = load_json("alphafold_prediction_P69905.json")
    del prediction[0]["pdbUrl"]
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=prediction)
    )
    respx.get(url__startswith=AF_FILES).mock(return_value=httpx.Response(404))

    with pytest.raises(SourceUnavailableError):
        await AlphaFoldClient().download_structure("P69905")


@respx.mock
async def test_alphafold_download_transport_error_falls_through_to_fallback() -> None:
    """A connection error on the published URL must not abort the chain.

    A transient network failure on pdbUrl is not evidence about the fallback,
    so the fallback still gets its turn — exactly as it does for a bad status.
    """
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=_prediction_with_stale_pdb_url())
    )
    primary = respx.get(f"{AF_FILES}AF-P69905-F1-model_v5.pdb").mock(
        side_effect=httpx.ConnectError("connection reset by peer")
    )
    fallback = respx.get(f"{AF_FILES}AF-P69905-F1-model_v6.pdb").mock(
        return_value=httpx.Response(200, content=b"HEADER FALLBACK END")
    )

    content, fmt = await AlphaFoldClient().download_structure("P69905")

    assert primary.called
    assert fallback.called
    assert fmt == "pdb"
    assert b"FALLBACK" in content


@respx.mock
async def test_alphafold_download_fails_only_once_every_leg_is_exhausted() -> None:
    """Transport error on the published URL + 404 on the fallback is an outage."""
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=_prediction_with_stale_pdb_url())
    )
    primary = respx.get(f"{AF_FILES}AF-P69905-F1-model_v5.pdb").mock(
        side_effect=httpx.ConnectError("connection reset by peer")
    )
    fallback = respx.get(f"{AF_FILES}AF-P69905-F1-model_v6.pdb").mock(
        return_value=httpx.Response(404)
    )

    with pytest.raises(SourceUnavailableError) as excinfo:
        await AlphaFoldClient().download_structure("P69905")

    assert primary.called
    assert fallback.called
    assert "could not be reached" in str(excinfo.value)


@respx.mock
async def test_alphafold_download_structure_bypasses_the_metadata_cache() -> None:
    """Spec 5.4: a cached payload must not be able to supply a stale pdbUrl."""
    prediction = respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=load_json("alphafold_prediction_P69905.json"))
    )
    respx.get(url__startswith=AF_FILES).mock(
        return_value=httpx.Response(200, content=b"HEADER TEST END")
    )
    client = AlphaFoldClient()

    await client.fetch_metadata("P69905")
    assert prediction.call_count == 1

    await client.download_structure("P69905")
    # Re-read rather than served from the entry fetch_metadata just cached.
    assert prediction.call_count == 2


@respx.mock
async def test_alphafold_download_structure_falls_back_to_latest_version_url() -> None:
    """Without a published pdbUrl, the guess uses the payload's `latestVersion` (6 here), not a hard-coded v4."""
    prediction = load_json("alphafold_prediction_P69905.json")
    del prediction[0]["pdbUrl"]
    assert prediction[0]["latestVersion"] == 6
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=prediction)
    )
    fallback = respx.get(f"{AF_FILES}AF-P69905-F1-model_v6.pdb").mock(
        return_value=httpx.Response(200, content=b"HEADER    FALLBACK\nEND\n")
    )

    content, fmt = await AlphaFoldClient().download_structure("P69905")

    assert fallback.called
    assert fmt == "pdb"
    assert b"FALLBACK" in content


@respx.mock
async def test_alphafold_download_structure_falls_back_to_default_version_when_latest_version_missing() -> None:
    """If the payload omits `latestVersion` entirely, the guess falls back to the documented default (v4)."""
    prediction = load_json("alphafold_prediction_P69905.json")
    del prediction[0]["pdbUrl"]
    del prediction[0]["latestVersion"]
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=prediction)
    )
    fallback = respx.get(f"{AF_FILES}AF-P69905-F1-model_v4.pdb").mock(
        return_value=httpx.Response(200, content=b"HEADER    FALLBACK\nEND\n")
    )

    content, fmt = await AlphaFoldClient().download_structure("P69905")

    assert fallback.called
    assert fmt == "pdb"
    assert b"FALLBACK" in content


# ------------------------------------------------------------------ UniProt


@respx.mock
async def test_uniprot_search_maps_entries() -> None:
    route = respx.get(url__startswith=UNIPROT_SEARCH).mock(
        return_value=httpx.Response(200, json=load_json("uniprot_search_insulin.json"))
    )

    results = await UniProtClient().search("insulin")

    params = route.calls.last.request.url.params
    assert params["query"] == "insulin"
    assert params["format"] == "json"

    assert [r.source_id for r in results] == ["P01308", "P06213"]
    assert results[0].source == "uniprot"
    assert results[0].title == "Insulin"
    assert results[0].organism == "Homo sapiens"
    assert results[0].description is not None
    assert "blood glucose" in results[0].description
    assert results[0].sequence_length == 110


@respx.mock
async def test_uniprot_fetch_metadata_normalises_and_caches() -> None:
    route = respx.get(UNIPROT_ENTRY_P01308).mock(
        return_value=httpx.Response(200, json=load_json("uniprot_entry_P01308.json"))
    )
    client = UniProtClient()

    meta = await client.fetch_metadata("p01308")
    assert meta["source_id"] == "P01308"
    assert meta["uniprot_id"] == "INS_HUMAN"
    assert meta["alphafold_accession"] == "P01308"
    assert meta["pdb_ids"] == ["1A7F", "1B9E"]
    assert meta["sequence_length"] == 110

    await client.fetch_metadata("P01308")
    assert route.call_count == 1


@respx.mock
async def test_uniprot_fetch_metadata_404_raises_not_found() -> None:
    respx.get(url__startswith="https://rest.uniprot.org/uniprotkb/").mock(
        return_value=httpx.Response(404)
    )
    with pytest.raises(SourceNotFoundError):
        await UniProtClient().fetch_metadata("Q0Q0Q0")


async def test_uniprot_rejects_malformed_accession_without_any_http() -> None:
    with pytest.raises(SourceNotFoundError):
        await UniProtClient().fetch_metadata("insulin")


@respx.mock
async def test_uniprot_download_structure_follows_alphafold_crossref() -> None:
    respx.get(UNIPROT_ENTRY_P01308).mock(
        return_value=httpx.Response(200, json=load_json("uniprot_entry_P01308.json"))
    )
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=load_json("alphafold_prediction_P69905.json"))
    )
    af_file = respx.get(url__startswith=AF_FILES).mock(
        return_value=httpx.Response(200, content=b"HEADER    VIA UNIPROT\nEND\n")
    )

    content, fmt = await UniProtClient().download_structure("P01308")

    assert af_file.called
    assert fmt == "pdb"
    assert b"VIA UNIPROT" in content


@respx.mock
async def test_uniprot_download_structure_bypasses_the_metadata_cache() -> None:
    """A stale AlphaFoldDB cross-reference must not misdirect the download."""
    entry = respx.get(UNIPROT_ENTRY_P01308).mock(
        return_value=httpx.Response(200, json=load_json("uniprot_entry_P01308.json"))
    )
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=load_json("alphafold_prediction_P69905.json"))
    )
    respx.get(url__startswith=AF_FILES).mock(
        return_value=httpx.Response(200, content=b"HEADER TEST END")
    )
    client = UniProtClient()

    await client.fetch_metadata("P01308")
    assert entry.call_count == 1

    await client.download_structure("P01308")
    assert entry.call_count == 2


@respx.mock
async def test_rcsb_search_enrichment_reuses_the_metadata_cache() -> None:
    """Deliberate: repeat searches must not re-fetch metadata for the same hits."""
    respx.post(RCSB_SEARCH).mock(
        return_value=httpx.Response(200, json=load_json("rcsb_search_insulin.json"))
    )
    entry, _ = _mock_rcsb_data_api()
    client = RCSBClient()

    await client.search("insulin")
    assert entry.call_count == 2  # one per hit in the fixture

    await client.search("insulin")
    assert entry.call_count == 2  # second search served entirely from cache


@respx.mock
async def test_uniprot_download_structure_without_alphafold_ref_raises_not_found() -> None:
    entry = load_json("uniprot_entry_P01308.json")
    entry["uniProtKBCrossReferences"] = [
        ref for ref in entry["uniProtKBCrossReferences"] if ref["database"] != "AlphaFoldDB"
    ]
    respx.get(UNIPROT_ENTRY_P01308).mock(return_value=httpx.Response(200, json=entry))

    with pytest.raises(SourceNotFoundError):
        await UniProtClient().download_structure("P01308")
