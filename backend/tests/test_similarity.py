"""P8 — UniRef transport, projection, and `GET /api/proteins/{uid}/similar`.

Fixtures `uniref_cluster_search_P01308.json` and
`uniref_members_UniRef50_P01308.json` are **real recorded responses**, captured
from `rest.uniprot.org` on 2026-08-23 — the live capture P6 could not make
because that environment's egress policy blocked the host.

All upstream calls are mocked with respx. Nothing reaches the network.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import app
from app.models.protein import ChainInfo, ProteinSummary
from app.models.similarity import DEFAULT_UNIREF_IDENTITY
from app.services import registry, similarity
from app.services.external import SourceNotFoundError, SourceUnavailableError
from app.services.uniprot import (
    UNIREF_SEARCH_URL,
    UniProtClient,
    normalise_cluster_id,
)
from tests.helpers import load_json

client = TestClient(app)

UID = "5555555555554555855555555555eeee"
CLUSTER_ID = "UniRef50_P01308"
MEMBERS_URL = f"https://rest.uniprot.org/uniref/{CLUSTER_ID}/members"


def cluster_payload() -> dict:
    return load_json("uniref_cluster_search_P01308.json")


def members_payload() -> dict:
    return load_json("uniref_members_UniRef50_P01308.json")


def register(**overrides: object) -> ProteinSummary:
    fields: dict[str, object] = {
        "id": UID,
        "source": "uniprot",
        "source_id": "P01308",
        "name": "Insulin",
        "organism": "Homo sapiens",
        "file_url": f"/api/proteins/{UID}/file",
        "file_format": "pdb",
        "chains": [ChainInfo(id=f"{UID}:A", label="A", sequence="FVNQ", residue_count=4)],
        "residue_count": 4,
        "atom_count": 30,
        "molecular_weight": 500.0,
        "has_plddt": True,
        "warnings": [],
    }
    fields.update(overrides)
    summary = ProteinSummary.model_validate(fields)
    registry.put(UID, summary)
    return summary


def mock_uniref() -> None:
    respx.get(UNIREF_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=cluster_payload())
    )
    respx.get(MEMBERS_URL).mock(return_value=httpx.Response(200, json=members_payload()))


# ------------------------------------------------------------- cluster ids


@pytest.mark.parametrize(
    "bad", ["../../etc/passwd", "UniRef70_P01308", "P01308", "UniRef50_", "uniref50_P01308"]
)
def test_cluster_id_validation_rejects_anything_not_a_uniref_id(bad: str) -> None:
    """The cluster id goes into a URL path, so its shape is checked first."""
    with pytest.raises(SourceNotFoundError):
        normalise_cluster_id(bad)


@pytest.mark.parametrize("good", ["UniRef50_P01308", "UniRef90_P01308", "UniRef100_A0A2I3HNQ8"])
def test_cluster_id_validation_accepts_all_three_levels(good: str) -> None:
    assert normalise_cluster_id(good) == good


# --------------------------------------------------------------- transport


@respx.mock
async def test_find_uniref_cluster_queries_by_membership_not_by_name() -> None:
    """A protein is only *named* after its cluster when it is the representative.

    Fetching `UniRef50_{accession}` directly would 404 for every other member,
    so the lookup must be a membership search.
    """
    route = respx.get(UNIREF_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=cluster_payload())
    )
    cluster = await UniProtClient().find_uniref_cluster("P01308")
    assert cluster is not None
    assert cluster["id"] == CLUSTER_ID
    query = route.calls[0].request.url.params["query"]
    assert "uniprot_id:P01308" in query
    assert "identity:0.5" in query


@respx.mock
async def test_find_uniref_cluster_returns_none_when_there_is_no_cluster() -> None:
    respx.get(UNIREF_SEARCH_URL).mock(return_value=httpx.Response(200, json={"results": []}))
    assert await UniProtClient().find_uniref_cluster("P01308") is None


@respx.mock
async def test_an_absent_cluster_is_cached_so_the_tab_does_not_requery() -> None:
    route = respx.get(UNIREF_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    uniprot = UniProtClient()
    assert await uniprot.find_uniref_cluster("P01308") is None
    assert await uniprot.find_uniref_cluster("P01308") is None
    assert route.call_count == 1


@respx.mock
async def test_cluster_lookups_are_cached_per_accession_and_level() -> None:
    route = respx.get(UNIREF_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=cluster_payload())
    )
    uniprot = UniProtClient()
    await uniprot.find_uniref_cluster("P01308", identity=0.5)
    await uniprot.find_uniref_cluster("P01308", identity=0.5)
    assert route.call_count == 1
    await uniprot.find_uniref_cluster("P01308", identity=0.9)
    assert route.call_count == 2


@respx.mock
async def test_cluster_lookups_do_not_collide_across_accessions() -> None:
    """Two proteins at the same clustering level are two different questions.

    A cache key that dropped the accession would hand the second protein the
    first one's homologs — a wrong answer that looks entirely plausible, since
    every field in it is real.
    """
    route = respx.get(UNIREF_SEARCH_URL).mock(
        side_effect=[
            httpx.Response(200, json=cluster_payload()),
            httpx.Response(
                200,
                json={"results": [{"id": "UniRef50_P00698", "name": "Cluster: Lysozyme C"}]},
            ),
        ]
    )
    uniprot = UniProtClient()

    first = await uniprot.find_uniref_cluster("P01308")
    second = await uniprot.find_uniref_cluster("P00698")

    assert route.call_count == 2
    assert first is not None and first["id"] == CLUSTER_ID
    assert second is not None and second["id"] == "UniRef50_P00698"


async def test_an_unsupported_identity_level_is_refused_before_any_request() -> None:
    """No `@respx.mock`: reaching the network here would fail the test."""
    with pytest.raises(SourceNotFoundError, match="0.5, 0.9 or 1.0"):
        await UniProtClient().find_uniref_cluster("P01308", identity=0.75)


@respx.mock
async def test_fetch_uniref_members_returns_the_member_records() -> None:
    route = respx.get(MEMBERS_URL).mock(
        return_value=httpx.Response(200, json=members_payload())
    )
    members = await UniProtClient().fetch_uniref_members(CLUSTER_ID)
    assert len(members) == 25
    assert members[0]["memberId"] == "INS_HUMAN"
    assert route.calls[0].request.url.params["size"] == "25"


@respx.mock
async def test_member_fetches_are_capped_at_the_per_source_maximum() -> None:
    route = respx.get(MEMBERS_URL).mock(
        return_value=httpx.Response(200, json=members_payload())
    )
    await UniProtClient().fetch_uniref_members(CLUSTER_ID, size=5000)
    assert route.calls[0].request.url.params["size"] == "25"


@respx.mock
async def test_member_pages_are_cached_per_cluster() -> None:
    """The Similarity tab is re-opened constantly; the second open must not be
    a second round trip to UniProt."""
    route = respx.get(MEMBERS_URL).mock(
        return_value=httpx.Response(200, json=members_payload())
    )
    uniprot = UniProtClient()

    first = await uniprot.fetch_uniref_members(CLUSTER_ID)
    second = await uniprot.fetch_uniref_members(CLUSTER_ID)

    assert route.call_count == 1
    assert len(first) == len(second) == 25


@respx.mock
async def test_the_member_fetch_drops_records_that_are_not_objects() -> None:
    """A stray null in `results` must not become a member with no fields."""
    respx.get(MEMBERS_URL).mock(
        return_value=httpx.Response(
            200, json={"results": [{"accessions": ["P01308"]}, "junk", None, 7]}
        )
    )
    members = await UniProtClient().fetch_uniref_members(CLUSTER_ID)
    assert members == [{"accessions": ["P01308"]}]


@respx.mock
async def test_the_member_fetch_validates_the_cluster_id_before_using_it() -> None:
    """The id is interpolated into a URL path, so it is checked first.

    `@respx.mock` with nothing mocked: were the guard dropped, the outbound
    request would fail this test rather than reach UniProt.
    """
    with pytest.raises(SourceNotFoundError):
        await UniProtClient().fetch_uniref_members("../../etc/passwd")


@respx.mock
async def test_a_uniref_404_is_an_absence_not_an_outage() -> None:
    """"UniProt has nothing for this accession" is an answer the user can act
    on; "UniProt is down" is one they can only retry. Collapsing the two turns
    a permanent empty result into an endless retry."""
    respx.get(UNIREF_SEARCH_URL).mock(return_value=httpx.Response(404))
    with pytest.raises(SourceNotFoundError):
        await UniProtClient().find_uniref_cluster("P01308")


@respx.mock
async def test_a_uniref_error_status_is_reported_as_that_status() -> None:
    """A 500 whose body happens to be valid JSON is still an outage.

    Falling through to the body would read an error document as a result and
    report "no cluster" for a protein that has one.
    """
    respx.get(UNIREF_SEARCH_URL).mock(
        return_value=httpx.Response(500, json={"messages": ["internal error"]})
    )
    with pytest.raises(SourceUnavailableError, match="HTTP 500"):
        await UniProtClient().find_uniref_cluster("P01308")


@respx.mock
async def test_uniref_rejects_a_payload_that_is_not_an_object() -> None:
    respx.get(UNIREF_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=["not", "an", "object"])
    )
    with pytest.raises(SourceUnavailableError, match="unexpected payload"):
        await UniProtClient().find_uniref_cluster("P01308")


@respx.mock
async def test_uniref_5xx_raises_unavailable() -> None:
    respx.get(UNIREF_SEARCH_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(SourceUnavailableError):
        await UniProtClient().find_uniref_cluster("P01308")


@respx.mock
async def test_uniref_non_json_body_raises_unavailable() -> None:
    respx.get(UNIREF_SEARCH_URL).mock(return_value=httpx.Response(200, text="<html>"))
    with pytest.raises(SourceUnavailableError, match="non-JSON"):
        await UniProtClient().find_uniref_cluster("P01308")


# -------------------------------------------------------------- projection


def build():
    return similarity.build_similar_proteins(
        UID,
        cluster_payload()["results"][0],
        members_payload()["results"],
        accession="P01308",
        note="test",
    )


def test_projection_reads_the_cluster_header() -> None:
    result = build()
    assert result.cluster_id == CLUSTER_ID
    assert result.cluster_name == "Cluster: Insulin"
    assert result.member_count == 35
    # 22, not 35: the cluster spans fewer organisms than it has members, so a
    # count that merely had to be positive could not tell the two fields apart.
    assert result.organism_count == 22
    assert result.identity_threshold == 0.5
    assert result.accession_resolved is True


def test_the_query_protein_is_not_one_of_its_own_similar_proteins() -> None:
    result = build()
    assert "P01308" not in [m.accession for m in result.members]
    # 25 recorded members: 20 UniProtKB entries (one of them the query) and 5
    # UniParc records with no accession at all — see the next test.
    assert len(result.members) == 19


def test_uniparc_members_are_skipped_because_they_have_no_accession() -> None:
    """Five of the 25 recorded members are UniParc records.

    UniParc holds sequences, not entries: they carry no UniProt accession, so
    there is nothing to link to and nothing to import. Listing them as rows
    with an empty accession would be worse than leaving them out.
    """
    recorded = members_payload()["results"]
    uniparc = [m for m in recorded if m.get("memberIdType") == "UniParc"]
    assert len(uniparc) == 5
    assert all(not m.get("accessions") for m in uniparc)
    assert len(build().members) == len(recorded) - len(uniparc) - 1


def test_projection_carries_the_fields_the_table_renders() -> None:
    gorilla = next(m for m in build().members if m.accession == "Q6YK33")
    assert gorilla.entry_id == "INS_GORGO"
    assert gorilla.protein_name == "Insulin"
    assert gorilla.organism == "Gorilla gorilla gorilla (Western lowland gorilla)"
    assert gorilla.taxon_id == 9595
    assert gorilla.sequence_length == 110
    assert gorilla.uniprot_url == "https://www.uniprot.org/uniprotkb/Q6YK33/entry"


def test_a_member_is_identified_by_its_primary_accession() -> None:
    """UniRef lists secondary accessions too; the first is the primary one.

    INS_MACFA is recorded as ["P30406", "P01309"] — importing P01309 would
    land on a demerged entry.
    """
    macaque = next(m for m in build().members if m.entry_id == "INS_MACFA")
    assert macaque.accession == "P30406"


def test_a_member_accession_is_normalised_before_it_is_compared() -> None:
    """UniRef spells accessions upper-case today.

    Both the self-exclusion and the deduplication are string comparisons, so
    they depend on that habit holding rather than on the comparison being made
    safe — and a lower-case query accession slipping through would list the
    protein among its own homologs.
    """
    members = members_payload()["results"]
    members.append({"memberId": "INS_SHOUTED", "accessions": ["p01308"]})
    members.append({"memberId": "INS_MUTTERED", "accessions": ["q6yk33"]})

    result = similarity.build_similar_proteins(
        UID, cluster_payload()["results"][0], members, accession="P01308", note="t"
    )

    accessions = [m.accession for m in result.members]
    assert "p01308" not in accessions
    assert "P01308" not in accessions
    assert all(a == a.upper() for a in accessions)
    assert len(accessions) == len(set(accessions))


def test_the_cluster_representative_is_flagged() -> None:
    """The recorded cluster's representative IS the query, so no member is
    flagged once the query is excluded — the flag must not land on someone else."""
    assert [m.accession for m in build().members if m.is_representative] == []


def test_the_representative_flag_lands_on_the_right_member() -> None:
    cluster = cluster_payload()["results"][0]
    result = similarity.build_similar_proteins(
        UID,
        cluster,
        members_payload()["results"],
        # BLAST from a different member of the same cluster: now the
        # representative (P01308) is a genuine "similar protein".
        accession="Q6YK33",
        note="test",
    )
    assert [m.accession for m in result.members if m.is_representative] == ["P01308"]


def test_truncation_is_stated_rather_than_implied() -> None:
    """The cluster holds 35 members; we asked for 25. Saying so beats implying
    the cluster is only as big as the page we fetched."""
    result = build()
    assert result.truncated is True
    assert result.member_count == 35


def test_projection_skips_members_with_no_accession() -> None:
    members = members_payload()["results"]
    members.append({"memberId": "GHOST", "accessions": []})
    result = similarity.build_similar_proteins(
        UID, cluster_payload()["results"][0], members, accession="P01308", note="t"
    )
    assert all(m.accession for m in result.members)


def test_projection_deduplicates_repeated_members() -> None:
    members = members_payload()["results"]
    duplicated = members + [members[1]]
    result = similarity.build_similar_proteins(
        UID, cluster_payload()["results"][0], duplicated, accession="P01308", note="t"
    )
    accessions = [m.accession for m in result.members]
    assert len(accessions) == len(set(accessions))


def test_empty_similar_is_a_successful_answer_not_an_error() -> None:
    result = similarity.empty_similar(UID, "no accession here")
    assert result.accession_resolved is False
    assert result.members == []
    assert result.resolution_note == "no accession here"


def test_an_empty_answer_still_reports_a_resolved_accession() -> None:
    """"We know which entry this is and it has no homologs" and "we could not
    work out which entry this is" are different answers, and the UI shows a
    different thing for each. An empty member list is not what tells them
    apart."""
    result = similarity.empty_similar(UID, "no cluster", accession="P01308")
    assert result.accession_resolved is True
    assert result.accession == "P01308"
    assert result.members == []


# ---------------------------------------------------------------- endpoint


@respx.mock
def test_similar_endpoint_returns_homologs_for_a_uniprot_import() -> None:
    register()
    mock_uniref()

    body = client.get(f"/api/proteins/{UID}/similar").json()

    assert body["accession"] == "P01308"
    assert body["cluster_id"] == CLUSTER_ID
    assert body["member_count"] == 35
    assert len(body["members"]) == 19
    assert body["members"][0]["accession"] != "P01308"


def test_similar_endpoint_is_200_and_empty_for_a_plain_upload() -> None:
    """No `@respx.mock`: an upload has no accession, so nothing may go upstream."""
    register(source="uploaded", source_id=None)

    response = client.get(f"/api/proteins/{UID}/similar")

    assert response.status_code == 200
    body = response.json()
    assert body["accession_resolved"] is False
    assert body["members"] == []
    assert "no database identifier" in body["resolution_note"]


@respx.mock
def test_similar_endpoint_explains_an_accession_with_no_cluster() -> None:
    register()
    respx.get(UNIREF_SEARCH_URL).mock(return_value=httpx.Response(200, json={"results": []}))

    body = client.get(f"/api/proteins/{UID}/similar").json()

    assert body["accession"] == "P01308"
    assert body["accession_resolved"] is True
    assert body["members"] == []
    assert "UniRef50" in body["resolution_note"]


@respx.mock
def test_the_endpoint_asks_for_the_clustering_level_it_reports() -> None:
    """The level searched and the level shown must be the same number.

    UniRef50 and UniRef100 answer different questions — 100 mostly returns the
    same protein under other accessions — so a response labelled 50 that was
    fetched at 100 is a wrong answer with a correct-looking label.
    """
    register()
    search = respx.get(UNIREF_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=cluster_payload())
    )
    respx.get(MEMBERS_URL).mock(return_value=httpx.Response(200, json=members_payload()))

    body = client.get(f"/api/proteins/{UID}/similar").json()

    assert body["identity_threshold"] == DEFAULT_UNIREF_IDENTITY
    query = search.calls[0].request.url.params["query"]
    assert f"identity:{body['identity_threshold']:.1f}" in query


@respx.mock
def test_a_cluster_with_no_identifier_is_explained_not_crashed() -> None:
    """Without an id there is no members URL to build.

    Saying so is a 200 with an explanation; letting the id through would
    interpolate None into a path and turn a UniProt oddity into a 500.
    """
    register()
    body = cluster_payload()
    body["results"][0].pop("id")
    respx.get(UNIREF_SEARCH_URL).mock(return_value=httpx.Response(200, json=body))
    members = respx.get(MEMBERS_URL).mock(
        return_value=httpx.Response(200, json=members_payload())
    )

    response = client.get(f"/api/proteins/{UID}/similar")

    assert response.status_code == 200
    payload = response.json()
    assert payload["members"] == []
    assert "no identifier" in payload["resolution_note"]
    assert members.call_count == 0


@respx.mock
def test_similar_endpoint_explains_a_uniref_404_rather_than_failing() -> None:
    """UniRef having nothing for an accession is an answer, not an outage.

    Same posture as `/annotations`: the user is told why the panel is empty
    instead of being handed an error they can only retry.
    """
    register()
    respx.get(UNIREF_SEARCH_URL).mock(return_value=httpx.Response(404))

    response = client.get(f"/api/proteins/{UID}/similar")

    assert response.status_code == 200
    body = response.json()
    assert body["accession"] == "P01308"
    assert body["members"] == []
    assert "no cluster" in body["resolution_note"]


@respx.mock
def test_similar_endpoint_refuses_a_malformed_uid_even_when_one_is_registered() -> None:
    """The registry is a plain dict and will answer for any key it was given,
    so a 404 for an *unknown* malformed uid cannot tell the shape guard from
    the lookup miss. The upstream route is mocked so a regression is caught
    here rather than by an outbound request."""
    summary = register()
    registry.put("not-a-storage-uid", summary)
    search = respx.get(UNIREF_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=cluster_payload())
    )

    response = client.get("/api/proteins/not-a-storage-uid/similar")

    assert response.status_code == 404
    assert search.call_count == 0


@respx.mock
def test_similar_endpoint_is_502_when_uniprot_is_unreachable() -> None:
    register()
    respx.get(UNIREF_SEARCH_URL).mock(return_value=httpx.Response(503))

    response = client.get(f"/api/proteins/{UID}/similar")

    assert response.status_code == 502
    assert "Try again" in response.json()["detail"]


def test_similar_endpoint_is_404_for_an_unknown_protein() -> None:
    assert client.get("/api/proteins/6666666666664666866666666666ffff/similar").status_code == 404


def test_similar_endpoint_is_404_for_a_malformed_uid() -> None:
    assert client.get("/api/proteins/..%2F..%2Fetc/similar").status_code == 404
