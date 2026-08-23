"""P9 — the Complex Portal client, its projection, and the endpoint.

Every upstream call is mocked with respx against fixtures recorded from
`www.ebi.ac.uk/intact/complex-ws` on 2026-08-23. Nothing in this file may reach
the network; `@respx.mock` fails the test if it tries.

The fixtures are real responses, not hand-written ones, which is what makes the
three facts this module is built on testable at all: the search over-matches on
free text, it indexes base accessions only, and the complexes that actually
contain a given protein are often the predicted ones.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import app
from app.models.protein import ChainInfo, ProteinSummary
from app.services import complexes as complexes_service
from app.services import registry
from app.services.complexes import (
    MAX_COMPLEXES_PER_QUERY,
    ComplexPortalClient,
    base_accession,
)
from app.services.external import SourceNotFoundError, SourceUnavailableError
from tests.helpers import load_json

client = TestClient(app)

COMPLEX_WS = "https://www.ebi.ac.uk/intact/complex-ws/search/"
UNIPROT_ENTRY = "https://rest.uniprot.org/uniprotkb/"
UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
RCSB_ENTRY = "https://data.rcsb.org/rest/v1/core/entry/"
RCSB_ENTITY = "https://data.rcsb.org/rest/v1/core/polymer_entity/"

UID = "1111111111114111811111111111aaaa"


def register(**overrides: object) -> ProteinSummary:
    """Put a summary in the registry so the endpoint can find it."""
    fields: dict[str, object] = {
        "id": UID,
        "source": "uploaded",
        "source_id": None,
        "name": "Test protein",
        "organism": None,
        "file_url": f"/api/proteins/{UID}/file",
        "file_format": "pdb",
        "chains": [ChainInfo(id=f"{UID}:A", label="A", sequence="TTCC", residue_count=4)],
        "residue_count": 4,
        "atom_count": 30,
        "molecular_weight": 400.0,
        "has_plddt": False,
        "warnings": [],
    }
    fields.update(overrides)
    summary = ProteinSummary.model_validate(fields)
    registry.put(UID, summary)
    return summary


def insulin() -> dict:
    return load_json("complex_portal_P01308.json")


def haemoglobin() -> dict:
    return load_json("complex_portal_P69905.json")


def nothing() -> dict:
    return load_json("complex_portal_P00698_empty.json")


def insulin_receptor() -> dict:
    """INSR — the case where the protein appears only as PRO chains."""
    return load_json("complex_portal_P06213.json")


def insulin_first_page() -> dict:
    """A real paginated response: 3 elements returned, 9 matches upstream."""
    return load_json("complex_portal_P01308_page1.json")


def build(body: dict, accession: str = "P01308"):
    return complexes_service.build_complexes(UID, body, accession=accession, note="test")


def one(payload, accession: str):
    """The single complex with this accession, or a clear assertion failure."""
    found = [c for c in payload.complexes if c.accession == accession]
    assert found, f"{accession} missing from {[c.accession for c in payload.complexes]}"
    return found[0]


# ------------------------------------------------------------ accession shape


def test_isoform_suffix_is_stripped_before_the_query() -> None:
    """Complex Portal indexes base accessions only.

    Verified against the live service: `search/P01308-1` returns zero results
    where `search/P01308` returns nine. Sending the suffixed form would make
    every isoform-imported protein look like it belongs to no complex.
    """
    assert base_accession("P01308-1") == "P01308"
    assert base_accession("P01308") == "P01308"
    assert base_accession("p01308-2") == "P01308"
    # A PRO chain id reduces to its parent accession the same way.
    assert base_accession("P06213-PRO_0000016689") == "P06213"
    # A ChEBI participant has no accession to reduce; it must survive intact so
    # it can never be mistaken for the queried protein.
    assert base_accession("CHEBI:30413") == "CHEBI:30413"


# ------------------------------------------------- the over-matching problem


def test_free_text_matches_that_do_not_contain_the_protein_are_dropped() -> None:
    """The load-bearing filter.

    Complex Portal's search is full text. Nine records match `P01308`, but the
    two insulin *receptor* complexes only name "Insulin (P01308)" in their
    curated description — they contain INSR chains and no insulin. Listing
    them as complexes containing insulin would be wrong biology.
    """
    payload = build(insulin())

    kept = {c.accession for c in payload.complexes}
    assert payload.search_matches == 9
    assert len(payload.complexes) == 7
    assert "CPX-26675" not in kept, "INSR complex contains no insulin"
    assert "CPX-16536" not in kept, "INSR-IGF1R hybrid contains no insulin"
    assert "CPX-19016" in kept


def test_every_kept_complex_actually_contains_the_query_protein() -> None:
    payload = build(insulin())

    assert payload.complexes, "fixture should keep at least one complex"
    for complex_ in payload.complexes:
        marked = [p for p in complex_.participants if p.is_query_protein]
        assert len(marked) == 1, f"{complex_.accession} should mark exactly one row"
        assert base_accession(marked[0].identifier) == "P01308"


def test_search_matches_reports_the_upstream_total_not_the_kept_count() -> None:
    """The dropped records stay visible in the payload rather than vanishing."""
    payload = build(insulin())

    assert payload.search_matches == 9
    assert payload.search_matches > len(payload.complexes)


def test_search_matches_comes_from_upstream_not_from_the_page_we_received() -> None:
    """A recorded first page: 3 elements returned, 9 matches upstream.

    Counting the elements in hand would under-report by six. This is the only
    fixture where the two numbers differ, which is exactly why it exists.
    """
    payload = build(insulin_first_page())

    assert len(payload.complexes) == 1, "two of the three are text-only matches"
    assert payload.search_matches == 9


def test_a_protein_participating_only_as_a_pro_chain_is_still_matched() -> None:
    """The case a plain string comparison silently loses.

    In CPX-16536 — the one *curated* complex INSR is in — P06213 appears only
    as the mature chains P06213-PRO_0000016689 and P06213-PRO_0000016687.
    Comparing identifiers without reducing them to the base accession drops
    that complex and leaves the protein looking like it is only ever in
    predicted ones.
    """
    payload = build(insulin_receptor(), accession="P06213")
    curated = one(payload, "CPX-16536")

    assert curated.predicted is False
    marked = [p for p in curated.participants if p.is_query_protein]
    assert {p.identifier for p in marked} == {
        "P06213-PRO_0000016689",
        "P06213-PRO_0000016687",
    }
    # The other subunit's chains belong to IGF1R and must not be marked.
    assert all(not p.is_query_protein for p in curated.participants if "P08069" in p.identifier)


# ------------------------------------------------------------ the projection


def test_complex_carries_name_organism_function_and_a_portal_link() -> None:
    payload = build(insulin())
    complex_ = one(payload, "CPX-19016")

    assert complex_.name == "INS:PRSS12"
    # "Homo sapiens; 9606" upstream — the taxon id is stripped off the name.
    assert complex_.organism == "Homo sapiens"
    assert complex_.url == "https://www.ebi.ac.uk/complexportal/complex/CPX-19016"


def test_predicted_and_curated_complexes_are_distinguished() -> None:
    """A predicted complex is an inference, not curated experimental evidence.

    Insulin is the case that makes this matter: every complex that actually
    contains P01308 is predicted and carries no curated function text, while
    the two records with real function text are the ones it is not in. Showing
    both kinds identically would present a prediction as curated knowledge.
    """
    predicted = one(build(insulin()), "CPX-19016")
    curated = one(build(haemoglobin(), accession="P69905"), "CPX-2158")

    assert predicted.predicted is True
    assert predicted.description is None, "predicted complexes carry no function text"
    assert curated.predicted is False
    assert curated.description is not None


def test_curated_complexes_sort_ahead_of_predicted_ones() -> None:
    """Order is imposed here, not inherited from upstream.

    Complex Portal ranks by Solr relevance and guarantees nothing about where
    predicted complexes land, so the recorded response is fed in reversed —
    real data, deliberately permuted on the one variable under test. Without
    the sort the panel would open on a prediction while a curated complex with
    a real function sat further down the pulldown.
    """
    recorded = haemoglobin()
    reversed_body = {**recorded, "elements": list(reversed(recorded["elements"]))}

    payload = build(reversed_body, accession="P69905")

    flags = [c.predicted for c in payload.complexes]
    assert flags == sorted(flags), f"curated must come first, got {flags}"
    assert flags[0] is False and flags[-1] is True, "fixture should carry both kinds"


def test_sorting_is_stable_within_each_group() -> None:
    """Relevance order must survive inside the curated and predicted groups."""
    payload = build(haemoglobin(), accession="P69905")

    curated = [c.accession for c in payload.complexes if not c.predicted]
    assert curated == ["CPX-2419", "CPX-2927", "CPX-2932", "CPX-2933", "CPX-2158"]


def test_curated_description_is_the_complex_function_the_client_asked_for() -> None:
    payload = build(haemoglobin(), accession="P69905")
    complex_ = one(payload, "CPX-2158")

    assert complex_.description is not None
    assert "oxygen" in complex_.description.lower()


def test_participant_table_carries_names_and_descriptions() -> None:
    payload = build(haemoglobin(), accession="P69905")
    participants = {p.identifier: p for p in one(payload, "CPX-2158").participants}

    assert set(participants) == {"P69905", "P68871", "CHEBI:30413"}
    assert participants["P68871"].name == "HBB"
    assert participants["P68871"].description == "Hemoglobin subunit beta"
    assert participants["P69905"].is_query_protein is True
    assert participants["P68871"].is_query_protein is False


def test_fixed_stoichiometry_renders_as_a_single_copy_number() -> None:
    payload = build(haemoglobin(), accession="P69905")
    participants = {p.identifier: p for p in one(payload, "CPX-2158").participants}

    haem = participants["CHEBI:30413"]
    assert haem.stoichiometry == "4"
    assert (haem.stoichiometry_min, haem.stoichiometry_max) == (4, 4)
    assert participants["P69905"].stoichiometry == "2"


def test_absent_stoichiometry_stays_none_rather_than_becoming_zero() -> None:
    """Most curated participants carry no stoichiometry at all.

    Rendering an unrecorded copy number as 0 or 1 would invent data; the table
    has to be able to say "not recorded".
    """
    payload = build(haemoglobin(), accession="P69905")
    participants = one(payload, "CPX-22475").participants

    assert all(p.stoichiometry is None for p in participants)
    assert all(p.stoichiometry_min is None for p in participants)


def test_a_stoichiometry_range_renders_as_a_range() -> None:
    """An optional participant is curated as minValue: 0, maxValue: 1."""
    assert complexes_service._format_stoichiometry(0, 1) == "0-1"
    assert complexes_service._format_stoichiometry(2, 4) == "2-4"
    assert complexes_service._stoichiometry("minValue: 0, maxValue: 1") == (0, 1)
    assert complexes_service._stoichiometry(None) == (None, None)
    assert complexes_service._stoichiometry("unparseable") == (None, None)


def test_non_protein_participants_keep_their_interactor_type() -> None:
    """Complex Portal curates small molecules and RNA as real participants."""
    payload = build(haemoglobin(), accession="P69905")
    participants = {p.identifier: p for p in one(payload, "CPX-2158").participants}

    assert participants["CHEBI:30413"].interactor_type == "small molecule"
    assert participants["P68871"].interactor_type == "protein"


def test_participant_links_are_upgraded_to_https() -> None:
    """Complex Portal ships its ChEBI links as plain http://."""
    payload = build(haemoglobin(), accession="P69905")
    participants = {p.identifier: p for p in one(payload, "CPX-2158").participants}

    assert participants["CHEBI:30413"].url == (
        "https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:30413"
    )
    assert participants["P68871"].url == "https://www.uniprot.org/uniprotkb/P68871/entry"


def test_a_non_http_participant_link_is_dropped_not_rendered() -> None:
    """These strings land in an `<a href>`; a javascript: URL is an XSS vector."""
    assert complexes_service._safe_url("javascript:alert(1)") is None
    assert complexes_service._safe_url("data:text/html,<script>") is None
    assert complexes_service._safe_url("not a url at all") is None
    assert complexes_service._safe_url(None) is None
    assert complexes_service._safe_url("https://example.org/x") == "https://example.org/x"


def test_a_protein_in_no_complex_is_a_valid_empty_payload() -> None:
    payload = build(nothing(), accession="P00698")

    assert payload.complexes == []
    assert payload.search_matches == 0
    assert payload.accession_resolved is True


def test_projection_survives_a_junk_payload() -> None:
    """Untrusted JSON must never raise out of a pure projection."""
    payload = build({"elements": "not a list", "totalNumberOfResults": "nonsense"})

    assert payload.complexes == []
    assert payload.search_matches == 0


def test_elements_without_an_accession_or_interactors_are_skipped() -> None:
    payload = build(
        {
            "totalNumberOfResults": 3,
            "elements": [
                "not a dict",
                {"complexName": "no accession", "interactors": [{"identifier": "P01308"}]},
                {"complexAC": "CPX-1", "interactors": ["junk", {"name": "no identifier"}]},
            ],
        }
    )

    assert payload.complexes == []
    assert payload.search_matches == 3


def test_empty_complexes_is_a_valid_payload() -> None:
    payload = complexes_service.empty_complexes(UID, "nothing to look up")

    assert payload.accession_resolved is False
    assert payload.accession is None
    assert payload.complexes == []
    assert payload.search_matches == 0
    assert payload.resolution_note == "nothing to look up"


# ----------------------------------------------------------------- the client


@respx.mock
async def test_search_queries_the_base_accession_and_caches() -> None:
    route = respx.get(url__startswith=COMPLEX_WS).mock(
        return_value=httpx.Response(200, json=insulin())
    )
    portal = ComplexPortalClient()

    first = await portal.search_by_accession("P01308-1")
    second = await portal.search_by_accession("p01308")

    assert first["totalNumberOfResults"] == 9
    assert second == first
    assert route.call_count == 1, "second lookup should be served from the cache"
    request = route.calls.last.request
    assert request.url.path.endswith("/complex-ws/search/P01308")
    assert request.url.params["number"] == str(MAX_COMPLEXES_PER_QUERY)


@respx.mock
async def test_search_404_raises_not_found() -> None:
    respx.get(url__startswith=COMPLEX_WS).mock(return_value=httpx.Response(404))

    with pytest.raises(SourceNotFoundError):
        await ComplexPortalClient().search_by_accession("P01308")


@respx.mock
@pytest.mark.parametrize("status", [500, 502, 503])
async def test_search_5xx_raises_unavailable(status: int) -> None:
    """The status code is what decides, not whether the body happens to parse.

    The body here is deliberately valid JSON of the right shape: if the status
    check were dropped, an error response would otherwise be read as a
    perfectly good "this protein is in no complex" answer.
    """
    respx.get(url__startswith=COMPLEX_WS).mock(
        return_value=httpx.Response(status, json={"totalNumberOfResults": 0, "elements": []})
    )

    with pytest.raises(SourceUnavailableError):
        await ComplexPortalClient().search_by_accession("P01308")


@respx.mock
async def test_search_404_with_a_parseable_body_still_raises_not_found() -> None:
    respx.get(url__startswith=COMPLEX_WS).mock(
        return_value=httpx.Response(404, json={"totalNumberOfResults": 0, "elements": []})
    )

    with pytest.raises(SourceNotFoundError):
        await ComplexPortalClient().search_by_accession("P01308")


@respx.mock
async def test_search_non_json_body_raises_unavailable() -> None:
    """The service answers an outage with an nginx HTML page, not JSON."""
    respx.get(url__startswith=COMPLEX_WS).mock(
        return_value=httpx.Response(200, text="<html>503</html>")
    )

    with pytest.raises(SourceUnavailableError):
        await ComplexPortalClient().search_by_accession("P01308")


@respx.mock
async def test_search_non_dict_body_raises_unavailable() -> None:
    respx.get(url__startswith=COMPLEX_WS).mock(return_value=httpx.Response(200, json=[1, 2]))

    with pytest.raises(SourceUnavailableError):
        await ComplexPortalClient().search_by_accession("P01308")


@respx.mock
async def test_search_transport_failure_raises_unavailable() -> None:
    respx.get(url__startswith=COMPLEX_WS).mock(side_effect=httpx.ConnectError("down"))

    with pytest.raises(SourceUnavailableError):
        await ComplexPortalClient().search_by_accession("P01308")


# --------------------------------------------------------------- the endpoint


@respx.mock
def test_unknown_protein_is_404() -> None:
    assert client.get(f"/api/proteins/{UID}/complexes").status_code == 404


@respx.mock
def test_malformed_uid_is_404() -> None:
    assert client.get("/api/proteins/not-a-uid/complexes").status_code == 404


@respx.mock
def test_uploaded_protein_returns_an_empty_but_valid_payload() -> None:
    """An upload has no accession, so the endpoint makes no outbound call.

    `@respx.mock` proves that: an unmocked request would fail the test.
    """
    register()

    response = client.get(f"/api/proteins/{UID}/complexes")

    assert response.status_code == 200
    body = response.json()
    assert body["accession_resolved"] is False
    assert body["accession"] is None
    assert body["complexes"] == []
    assert body["search_matches"] == 0
    assert "no database identifier" in body["resolution_note"]


@respx.mock
@pytest.mark.parametrize("source", ["uniprot", "alphafold"])
def test_uniprot_and_alphafold_imports_resolve_straight_from_source_id(source: str) -> None:
    register(source=source, source_id="P01308")
    respx.get(url__startswith=COMPLEX_WS).mock(
        return_value=httpx.Response(200, json=insulin())
    )

    body = client.get(f"/api/proteins/{UID}/complexes").json()

    assert body["accession"] == "P01308"
    assert body["accession_resolved"] is True
    assert body["query"] == "P01308"
    assert len(body["complexes"]) == 7
    assert body["search_matches"] == 9


@respx.mock
def test_rcsb_import_maps_through_the_polymer_entity_then_queries_the_portal() -> None:
    """The accession is resolved by the same helper the annotations tab uses."""
    register(source="rcsb", source_id="1CRN")
    respx.get(url__startswith=RCSB_ENTRY).mock(
        return_value=httpx.Response(200, json=load_json("rcsb_entry_1CRN.json"))
    )
    respx.get(url__startswith=RCSB_ENTITY).mock(
        return_value=httpx.Response(
            200, json=load_json("rcsb_polymer_entity_1CRN_1.json")
        )
    )
    portal = respx.get(url__startswith=COMPLEX_WS).mock(
        return_value=httpx.Response(200, json=nothing())
    )

    body = client.get(f"/api/proteins/{UID}/complexes").json()

    assert body["accession_resolved"] is True
    assert body["complexes"] == []
    assert portal.call_count == 1


@respx.mock
def test_portal_outage_on_a_known_accession_is_a_502_not_a_500() -> None:
    register(source="uniprot", source_id="P01308")
    respx.get(url__startswith=COMPLEX_WS).mock(return_value=httpx.Response(503))

    response = client.get(f"/api/proteins/{UID}/complexes")

    assert response.status_code == 502
    assert "Complex Portal" in response.json()["detail"]


@respx.mock
def test_portal_404_degrades_to_an_empty_payload_rather_than_an_error() -> None:
    register(source="uniprot", source_id="P01308")
    respx.get(url__startswith=COMPLEX_WS).mock(return_value=httpx.Response(404))

    response = client.get(f"/api/proteins/{UID}/complexes")

    assert response.status_code == 200
    body = response.json()
    assert body["accession_resolved"] is False
    assert body["accession"] == "P01308"
    assert body["query"] == "P01308"
    assert body["complexes"] == []


@respx.mock
def test_invalid_accession_on_the_summary_never_reaches_the_portal() -> None:
    """A junk source_id resolves to no accession, so nothing is requested."""
    register(source="uniprot", source_id="not-an-accession")

    body = client.get(f"/api/proteins/{UID}/complexes").json()

    assert body["accession_resolved"] is False
    assert body["complexes"] == []


@respx.mock
def test_response_shape_matches_the_frontend_contract() -> None:
    """Pins the wire format the Complexes tab reads."""
    register(source="uniprot", source_id="P69905")
    respx.get(url__startswith=COMPLEX_WS).mock(
        return_value=httpx.Response(200, json=haemoglobin())
    )

    body = client.get(f"/api/proteins/{UID}/complexes").json()

    assert set(body) == {
        "id",
        "accession",
        "accession_resolved",
        "resolution_note",
        "query",
        "complexes",
        "search_matches",
    }
    assert set(body["complexes"][0]) == {
        "accession",
        "name",
        "organism",
        "description",
        "predicted",
        "url",
        "participants",
    }
    assert set(body["complexes"][0]["participants"][0]) == {
        "identifier",
        "name",
        "description",
        "interactor_type",
        "organism",
        "stoichiometry",
        "stoichiometry_min",
        "stoichiometry_max",
        "url",
        "is_query_protein",
    }
