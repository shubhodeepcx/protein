"""P8 — `POST /api/blast` and `GET /api/blast/{job_id}`.

The contract these tests exist to defend: **submit does not wait**. A BLAST
search takes 30 s to several minutes, so a submit that blocked would be a
request that times out in a proxy somewhere and takes the results with it.

All upstream calls are mocked with respx. Nothing reaches the network.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from urllib.parse import quote

from app.main import app
from app.models.protein import ChainInfo, ProteinSummary
from app.services import blast_jobs, registry
from app.services.blast import BASE_URL
from tests.helpers import load_json

client = TestClient(app)

RUN_URL = f"{BASE_URL}/run/"
JOB_ID = "ncbiblast-R20191128-094014-0332-71107816-p1m"
STATUS_URL = f"{BASE_URL}/status/{JOB_ID}"
RESULT_URL = f"{BASE_URL}/result/{JOB_ID}/json"

UID = "3333333333334333833333333333cccc"
MISSING_UID = "4444444444444444844444444444dddd"

LONG_CHAIN = "MALRKGGLALALLLLSWVALGPRSLEGADPGTPGEAEGPACPAACVCSYDDDADELSVFCS"
SHORT_CHAIN = "MKWVTFISLL"


def payload() -> dict:
    return load_json("ebi_ncbiblast_result_P35858.json")


def register(**overrides: object) -> ProteinSummary:
    fields: dict[str, object] = {
        "id": UID,
        "source": "rcsb",
        "source_id": "1CRN",
        "name": "Test protein",
        "organism": None,
        "file_url": f"/api/proteins/{UID}/file",
        "file_format": "pdb",
        "chains": [
            ChainInfo(id=f"{UID}:A", label="A", sequence=LONG_CHAIN, residue_count=len(LONG_CHAIN)),
            ChainInfo(id=f"{UID}:B", label="B", sequence=SHORT_CHAIN, residue_count=len(SHORT_CHAIN)),
        ],
        "residue_count": len(LONG_CHAIN) + len(SHORT_CHAIN),
        "atom_count": 500,
        "molecular_weight": 8000.0,
        "has_plddt": False,
        "warnings": [],
    }
    fields.update(overrides)
    summary = ProteinSummary.model_validate(fields)
    registry.put(UID, summary)
    return summary


def submitted_form(route) -> dict[str, str]:
    from urllib.parse import parse_qs

    raw = route.calls[0].request.content.decode()
    return {k: v[0] for k, v in parse_qs(raw).items()}


# ------------------------------------------------------------------ submit


@respx.mock
def test_submit_returns_a_job_id_immediately_and_does_not_poll() -> None:
    """The whole point of the async flow: one upstream call, then get out."""
    run = respx.post(RUN_URL).mock(return_value=httpx.Response(200, text=JOB_ID))
    status = respx.get(STATUS_URL).mock(return_value=httpx.Response(200, text="RUNNING"))
    result = respx.get(RESULT_URL).mock(return_value=httpx.Response(200, json=payload()))

    response = client.post("/api/blast", json={"sequence": "MALRKGGLALALL"})

    assert response.status_code == 202
    body = response.json()
    assert body["job_id"] == JOB_ID
    assert body["status"] == "QUEUED"
    assert body["poll_url"] == f"/api/blast/{JOB_ID}"
    assert body["query_length"] == 13
    assert body["query_source"] == "pasted sequence"
    assert run.call_count == 1
    # Submit must not have waited on the search in any way.
    assert status.call_count == 0
    assert result.call_count == 0


@respx.mock
def test_submit_from_a_stored_protein_uses_its_longest_chain() -> None:
    """Same convention analytics already uses for the "primary" chain."""
    register()
    run = respx.post(RUN_URL).mock(return_value=httpx.Response(200, text=JOB_ID))

    response = client.post("/api/blast", json={"protein_id": UID})

    assert response.status_code == 202
    assert submitted_form(run)["sequence"] == LONG_CHAIN
    assert response.json()["query_source"] == "1CRN chain A"
    assert response.json()["query_length"] == len(LONG_CHAIN)


@respx.mock
def test_submit_can_name_a_specific_chain() -> None:
    register()
    run = respx.post(RUN_URL).mock(return_value=httpx.Response(200, text=JOB_ID))

    response = client.post("/api/blast", json={"protein_id": UID, "chain_id": "b"})

    assert response.status_code == 202
    assert submitted_form(run)["sequence"] == SHORT_CHAIN
    assert response.json()["query_source"] == "1CRN chain B"


def test_submit_with_an_unknown_chain_lists_the_available_ones() -> None:
    register()
    response = client.post("/api/blast", json={"protein_id": UID, "chain_id": "Z"})
    assert response.status_code == 400
    assert "Available: A, B" in response.json()["detail"]


def test_submit_for_an_unknown_protein_is_404() -> None:
    response = client.post("/api/blast", json={"protein_id": MISSING_UID})
    assert response.status_code == 404


def test_submit_with_a_malformed_uid_is_404_not_500() -> None:
    response = client.post("/api/blast", json={"protein_id": "../../etc/passwd"})
    assert response.status_code == 404


def test_submit_needs_exactly_one_query_source() -> None:
    assert client.post("/api/blast", json={}).status_code == 422
    assert (
        client.post("/api/blast", json={"protein_id": UID, "sequence": "MA"}).status_code
        == 422
    )


def test_submit_rejects_a_sequence_with_junk_characters() -> None:
    response = client.post("/api/blast", json={"sequence": "MALR1234"})
    assert response.status_code == 400
    assert "amino-acid or nucleotide" in response.json()["detail"]


@respx.mock
def test_submit_forwards_the_program_and_database_the_caller_chose() -> None:
    run = respx.post(RUN_URL).mock(return_value=httpx.Response(200, text=JOB_ID))

    response = client.post(
        "/api/blast",
        json={
            "sequence": "ACGTACGTACGT",
            "program": "blastx",
            "database": "uniprotkb_swissprot",
            "exp": "10",
            "alignments": 20,
            "scores": 20,
        },
    )

    assert response.status_code == 202
    form = submitted_form(run)
    assert form["program"] == "blastx"
    assert form["database"] == "uniprotkb_swissprot"
    # blastx takes a NUCLEOTIDE query — sending stype=protein makes EBI reject it.
    assert form["stype"] == "dna"
    assert form["exp"] == "10"
    assert form["alignments"] == "20"


@respx.mock
def test_a_rejected_submission_is_400_not_502() -> None:
    """EBI said the parameters are wrong. Retrying them would fail identically."""
    respx.post(RUN_URL).mock(
        return_value=httpx.Response(400, text="Invalid parameter value")
    )
    response = client.post("/api/blast", json={"sequence": "MALRKGG"})
    assert response.status_code == 400
    assert "Invalid parameter value" in response.json()["detail"]


@respx.mock
def test_an_unreachable_ebi_is_502() -> None:
    respx.post(RUN_URL).mock(return_value=httpx.Response(500))
    response = client.post("/api/blast", json={"sequence": "MALRKGG"})
    assert response.status_code == 502


@respx.mock
def test_a_structure_with_no_chains_cannot_be_blasted() -> None:
    register(chains=[], residue_count=0)
    response = client.post("/api/blast", json={"protein_id": UID})
    assert response.status_code == 400
    assert "no protein chains" in response.json()["detail"]


# -------------------------------------------------------------------- poll


@respx.mock
def test_poll_reports_running_without_results() -> None:
    respx.post(RUN_URL).mock(return_value=httpx.Response(200, text=JOB_ID))
    respx.get(STATUS_URL).mock(return_value=httpx.Response(200, text="RUNNING"))
    client.post("/api/blast", json={"sequence": "MALRKGG"})

    body = client.get(f"/api/blast/{JOB_ID}").json()

    assert body["status"] == "RUNNING"
    assert body["finished"] is False
    assert body["result"] is None
    assert body["elapsed_seconds"] >= 0
    assert body["poll_count"] == 1
    assert "30 s to a few minutes" in body["message"]


@respx.mock
def test_poll_delivers_results_once_the_job_finishes() -> None:
    respx.post(RUN_URL).mock(return_value=httpx.Response(200, text=JOB_ID))
    respx.get(STATUS_URL).mock(return_value=httpx.Response(200, text="FINISHED"))
    respx.get(RESULT_URL).mock(return_value=httpx.Response(200, json=payload()))
    client.post("/api/blast", json={"sequence": "MALRKGG"})

    body = client.get(f"/api/blast/{JOB_ID}").json()

    assert body["status"] == "FINISHED"
    assert body["finished"] is True
    assert body["result"]["hit_count"] == 6
    top = body["result"]["hits"][0]
    assert top["accession"] == "P35858"
    assert top["identity_percent"] == 100.0
    assert top["expect"] == 0.0
    assert top["uniprot_accession"] == "P35858"


def test_poll_for_an_unknown_job_is_404_with_an_actionable_message() -> None:
    response = client.get(f"/api/blast/{JOB_ID}")
    assert response.status_code == 404
    assert "run the search again" in response.json()["detail"]


@pytest.mark.parametrize("bad", ["job id", "a b", "job\tid", "id;rm -rf"])
def test_poll_rejects_a_malformed_job_id_before_going_upstream(bad: str) -> None:
    """`@respx.mock` is absent on purpose: any outbound call here fails the test.

    The assertion is on the *id-shape* 404, not the "no such job" one, so the
    test proves the guard ran rather than the request having been routed
    somewhere harmless by accident.
    """
    response = client.get(f"/api/blast/{quote(bad, safe='')}")
    assert response.status_code == 404
    assert response.json()["detail"] == "BLAST job not found"


def test_a_path_traversal_job_id_never_reaches_a_handler() -> None:
    """Encoded slashes are normalised before routing, so this 404s at the router.

    Kept because it is the attack someone would actually try, and a future
    router change that started passing it through must not go unnoticed.
    """
    response = client.get("/api/blast/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code == 404


@respx.mock
def test_the_job_survives_the_user_navigating_away_and_back() -> None:
    """Polling is stateless on the client's side beyond holding the job id."""
    respx.post(RUN_URL).mock(return_value=httpx.Response(200, text=JOB_ID))
    respx.get(STATUS_URL).mock(
        side_effect=[
            httpx.Response(200, text="RUNNING"),
            httpx.Response(200, text="FINISHED"),
        ]
    )
    respx.get(RESULT_URL).mock(return_value=httpx.Response(200, json=payload()))

    job_id = client.post("/api/blast", json={"sequence": "MALRKGG"}).json()["job_id"]
    assert client.get(f"/api/blast/{job_id}").json()["status"] == "RUNNING"

    # ... user navigates to another page and comes back, holding only the id.
    later = client.get(f"/api/blast/{job_id}").json()
    assert later["status"] == "FINISHED"
    assert later["result"]["hit_count"] == 6


@respx.mock
def test_the_registry_is_the_module_singleton_the_router_reads() -> None:
    """Guards the seam the conftest fixture swaps: a second registry would make
    every submitted job unpollable."""
    respx.post(RUN_URL).mock(return_value=httpx.Response(200, text=JOB_ID))
    client.post("/api/blast", json={"sequence": "MALRKGG"})
    assert blast_jobs.get_registry().get(JOB_ID) is not None
