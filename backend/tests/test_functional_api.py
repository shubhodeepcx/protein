"""A5 — `GET /api/proteins/{uid}/functional-regions` end to end.

Every upstream call is mocked with respx against fixtures recorded on
2026-08-24; `@respx.mock` fails the test if anything reaches the network.

The route's one deliberate divergence from `/annotations` and `/complexes` is
under test here: a UniProt outage is **not** a 502. The observed half of this
payload — bound ligands, their contact residues, accessibility, hydropathy,
charge — is measured from the coordinate file and does not depend on UniProt
being reachable, so discarding it to report an upstream failure would be the
wrong trade.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import app
from app.services import registry
from app.services.parser import parse
from app.services.uniprot import FUNCTIONAL_FIELD_NAMES, UniProtClient
from app.storage import local as storage
from tests.helpers import FIXTURES, load_json

client = TestClient(app)

UNIPROT_ENTRY = "https://rest.uniprot.org/uniprotkb/"
UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
RCSB_ENTRY = "https://data.rcsb.org/rest/v1/core/entry/"
RCSB_ENTITY = "https://data.rcsb.org/rest/v1/core/polymer_entity/"

ROUTE = "/api/proteins/{uid}/functional-regions"


def lysozyme_entry() -> dict:
    return load_json("uniprot_functional_P00698.json")


def register_lysozyme(source: str = "rcsb", source_id: str | None = "1HEW") -> str:
    """Store 1HEW on disk and in the registry, and return its uid.

    Goes through the real parser rather than a hand-built `ProteinSummary`: the
    endpoint's whole job is to relate curated positions to what the parser
    read, so a summary invented here would let a numbering bug pass unseen.
    """
    uid, path = storage.store_upload((FIXTURES / "1HEW.pdb").read_bytes(), "pdb")
    registry.put(uid, parse(path, uid, source=source, source_id=source_id))  # type: ignore[arg-type]
    return uid


def uniprot_ok() -> respx.Route:
    return respx.get(url__startswith=UNIPROT_ENTRY).mock(
        return_value=httpx.Response(200, json=lysozyme_entry())
    )


# --------------------------------------------------------------- the happy path


@respx.mock
def test_endpoint_places_the_curated_sites_on_the_right_residues() -> None:
    """Glu35, Asp52, Asp101 — over the wire, in the selection key format."""
    uid = register_lysozyme(source="uniprot", source_id="P00698")
    uniprot_ok()

    body = client.get(ROUTE.format(uid=uid)).json()

    assert body["accession"] == "P00698"
    assert body["accession_resolved"] is True
    assert [
        (site["uniprot_start"], site["positions"][0]["key"], site["positions"][0]["residue"])
        for site in body["active_sites"]
    ] == [(53, "A:35", "E"), (70, "A:52", "D")]
    (binding,) = body["binding_sites"]
    assert binding["positions"][0]["key"] == "A:101"


@respx.mock
def test_endpoint_asks_uniprot_for_the_functional_field_set() -> None:
    """Including `sequence` — without it there is nothing to align through."""
    uid = register_lysozyme(source="uniprot", source_id="P00698")
    route = uniprot_ok()

    client.get(ROUTE.format(uid=uid))

    fields = route.calls.last.request.url.params["fields"].split(",")
    assert set(fields) == set(FUNCTIONAL_FIELD_NAMES)
    assert "sequence" in fields
    assert "ft_binding" in fields


@respx.mock
def test_endpoint_reports_observed_ligands_and_their_contacts() -> None:
    uid = register_lysozyme(source="uniprot", source_id="P00698")
    uniprot_ok()

    body = client.get(ROUTE.format(uid=uid)).json()

    assert [ligand["component"] for ligand in body["ligands"]] == ["NAG", "NAG", "NAG"]
    assert body["contact_cutoff"] == 4.0
    for ligand in body["ligands"]:
        assert ligand["provenance"] == "structure"
        assert ligand["contacts"]


@respx.mock
def test_endpoint_marks_converging_evidence_first() -> None:
    uid = register_lysozyme(source="uniprot", source_id="P00698")
    uniprot_ok()

    body = client.get(ROUTE.format(uid=uid)).json()

    top = body["priority_residues"][0]
    assert top["key"] == "A:101"
    assert sorted(top["provenance"]) == ["structure", "uniprot"]
    assert top["evidence_kinds"] == 2


@respx.mock
def test_endpoint_returns_the_surface_profile_per_chain() -> None:
    uid = register_lysozyme(source="uniprot", source_id="P00698")
    uniprot_ok()

    body = client.get(ROUTE.format(uid=uid)).json()

    (profile,) = body["surface"]
    assert profile["chain"] == "A"
    assert len(profile["hydropathy"]) == len(profile["sequence"]) == 129
    assert len(profile["charge"]) == 129
    assert len(profile["relative_accessibility"]) == 129
    assert profile["surface_mean_hydropathy"] is not None


@respx.mock
def test_endpoint_publishes_the_chain_mapping_it_used() -> None:
    """The evidence for every placement travels with the placements."""
    uid = register_lysozyme(source="uniprot", source_id="P00698")
    uniprot_ok()

    body = client.get(ROUTE.format(uid=uid)).json()

    (mapping,) = body["chain_mappings"]
    assert mapping["mapped"] is True
    assert mapping["uniprot_start"] == 19
    assert "UniProt 19-147 covers chain A residues 1-129" in mapping["offset_note"]


@respx.mock
def test_endpoint_always_says_it_does_not_predict_pockets() -> None:
    uid = register_lysozyme(source="uniprot", source_id="P00698")
    uniprot_ok()

    body = client.get(ROUTE.format(uid=uid)).json()

    assert any("does not predict pockets" in note for note in body["notes"])


# --------------------------------------------------- degrading, not failing


@respx.mock
def test_a_uniprot_outage_keeps_the_observed_half() -> None:
    """Not a 502. The ligands are in the file; UniProt being down changes nothing."""
    uid = register_lysozyme(source="uniprot", source_id="P00698")
    respx.get(url__startswith=UNIPROT_ENTRY).mock(return_value=httpx.Response(503))

    response = client.get(ROUTE.format(uid=uid))

    assert response.status_code == 200
    body = response.json()
    assert body["accession"] == "P00698"
    assert body["active_sites"] == []
    assert len(body["ligands"]) == 3
    assert body["surface"]
    assert any("UniProt could not be reached" in note for note in body["notes"])


@respx.mock
def test_an_unknown_accession_says_so_and_keeps_the_observed_half() -> None:
    uid = register_lysozyme(source="uniprot", source_id="P00698")
    respx.get(url__startswith=UNIPROT_ENTRY).mock(return_value=httpx.Response(404))

    body = client.get(ROUTE.format(uid=uid)).json()

    assert body["active_sites"] == []
    assert len(body["ligands"]) == 3
    assert any("no entry for accession P00698" in note for note in body["notes"])


@respx.mock
def test_a_plain_upload_needs_no_network_at_all() -> None:
    """No accession to resolve, so nothing is fetched — `@respx.mock` proves it."""
    uid = register_lysozyme(source="uploaded", source_id=None)

    body = client.get(ROUTE.format(uid=uid)).json()

    assert body["accession_resolved"] is False
    assert body["chain_mappings"] == []
    assert len(body["ligands"]) == 3
    assert body["priority_residues"]
    assert any("No UniProt entry could be resolved" in note for note in body["notes"])


@respx.mock
def test_rcsb_import_resolves_through_the_same_helper_the_other_tabs_use() -> None:
    uid = register_lysozyme(source="rcsb", source_id="1CRN")
    respx.get(url__startswith=RCSB_ENTRY).mock(
        return_value=httpx.Response(200, json=load_json("rcsb_entry_1CRN.json"))
    )
    respx.get(url__startswith=RCSB_ENTITY).mock(
        return_value=httpx.Response(
            200, json=load_json("rcsb_polymer_entity_1CRN_1.json")
        )
    )
    entry = respx.get(url__startswith=UNIPROT_ENTRY).mock(
        return_value=httpx.Response(200, json=lysozyme_entry())
    )

    body = client.get(ROUTE.format(uid=uid)).json()

    assert body["accession_resolved"] is True
    assert entry.call_count == 1


# ---------------------------------------------------------------- 404 paths


@respx.mock
def test_unknown_uid_is_404() -> None:
    assert client.get(ROUTE.format(uid="0" * 32)).status_code == 404


@respx.mock
def test_malformed_uid_is_404_without_reflecting_the_input() -> None:
    response = client.get(ROUTE.format(uid="not-a-uid"))
    assert response.status_code == 404
    assert "not-a-uid" not in response.text


@respx.mock
def test_a_registered_protein_whose_file_is_gone_is_404() -> None:
    uid = register_lysozyme(source="uploaded", source_id=None)
    storage.get_file(uid).unlink()

    assert client.get(ROUTE.format(uid=uid)).status_code == 404


# -------------------------------------------------------------- the client


@respx.mock
async def test_functional_fetch_is_cached_separately_from_annotations() -> None:
    """Two field sets, one cache. A shared key would serve half a payload.

    The annotation entry carries no `sequence` and the functional entry carries
    no GO terms, so a collision would not error — it would quietly return a
    panel with nothing in it.
    """
    uniprot = UniProtClient()
    functional_route = respx.get(
        url__startswith=UNIPROT_ENTRY, params__contains={"fields": ",".join(FUNCTIONAL_FIELD_NAMES)}
    ).mock(return_value=httpx.Response(200, json=lysozyme_entry()))
    annotation_route = respx.get(url__startswith=UNIPROT_ENTRY).mock(
        return_value=httpx.Response(200, json=load_json("uniprot_annotations_P00533.json"))
    )

    first = await uniprot.fetch_functional("P00698")
    await uniprot.fetch_annotations("P00698")
    second = await uniprot.fetch_functional("P00698")

    assert "sequence" in first
    assert first == second
    assert functional_route.call_count == 1, "second functional call should be cached"
    assert annotation_route.call_count == 1


@respx.mock
async def test_functional_fetch_rejects_a_malformed_accession() -> None:
    from app.services.external import SourceNotFoundError

    with pytest.raises(SourceNotFoundError):
        await UniProtClient().fetch_functional("../etc/passwd")
