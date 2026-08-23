"""P8 — EBI NCBI BLAST transport, job policy, result projection, and endpoints.

Every upstream call is mocked with respx against a recorded fixture. Nothing in
this file may reach the network; `@respx.mock` (assert_all_mocked=True) fails
the test if it tries.

`ebi_ncbiblast_result_P35858.json` is a **real recorded response**: EBI's own
published `example_blastp.json` from github.com/ebi-jdispatcher/sss_json_schema,
trimmed to its first 6 hits so the fixture is the same size as its neighbours.
Nothing inside a hit was edited, so an assertion here is an assertion about the
shape EBI actually emits — a hand-written fixture would prove nothing.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.blast import (
    MAX_QUERY_RESIDUES,
    BlastSubmitRequest,
    normalise_sequence,
)
from app.models.protein import ChainInfo, ProteinSummary
from app.services import registry
from app.services.blast import (
    BASE_URL,
    DEFAULT_CONTACT_EMAIL,
    BlastRequestRejected,
    EBIBlastClient,
    contact_email,
    validate_job_id,
)
from app.services.external import SourceNotFoundError, SourceUnavailableError
from tests.helpers import load_json

client = TestClient(app)

RUN_URL = f"{BASE_URL}/run/"
JOB_ID = "ncbiblast-R20191128-094014-0332-71107816-p1m"
STATUS_URL = f"{BASE_URL}/status/{JOB_ID}"
RESULT_URL = f"{BASE_URL}/result/{JOB_ID}/json"
TYPES_URL = f"{BASE_URL}/resulttypes/{JOB_ID}"

UID = "2222222222224222822222222222bbbb"


def blastp_payload() -> dict:
    return load_json("ebi_ncbiblast_result_P35858.json")


def register(**overrides: object) -> ProteinSummary:
    fields: dict[str, object] = {
        "id": UID,
        "source": "uploaded",
        "source_id": None,
        "name": "Test protein",
        "organism": None,
        "file_url": f"/api/proteins/{UID}/file",
        "file_format": "pdb",
        "chains": [
            ChainInfo(id=f"{UID}:A", label="A", sequence="TTCCPSIVARSNFNVCRLPGTPEA", residue_count=24),
            ChainInfo(id=f"{UID}:B", label="B", sequence="MKWVTF", residue_count=6),
        ],
        "residue_count": 30,
        "atom_count": 200,
        "molecular_weight": 3000.0,
        "has_plddt": False,
        "warnings": [],
    }
    fields.update(overrides)
    summary = ProteinSummary.model_validate(fields)
    registry.put(UID, summary)
    return summary


# --------------------------------------------------------------- sequences


def test_normalise_sequence_strips_fasta_header_and_whitespace() -> None:
    raw = ">sp|P35858|ALS_HUMAN Description\nmalr kggl\nALALL\n"
    assert normalise_sequence(raw) == "MALRKGGLALALL"


def test_normalise_sequence_rejects_non_residue_characters() -> None:
    with pytest.raises(ValueError, match="not amino-acid or nucleotide"):
        normalise_sequence("MALR1KGG")


def test_normalise_sequence_rejects_empty_after_header_removal() -> None:
    with pytest.raises(ValueError, match="empty"):
        normalise_sequence(">just a header\n\n")


def test_oversized_query_is_refused_not_truncated() -> None:
    """A query too long to run is an error, never a silently shortened search.

    BLASTing a prefix and labelling the answer with the whole protein's name
    would be a wrong answer presented as a right one.
    """
    with pytest.raises(ValueError, match=r"maximum accepted"):
        normalise_sequence("A" * (MAX_QUERY_RESIDUES + 1))


def test_query_at_the_limit_is_accepted() -> None:
    assert len(normalise_sequence("A" * MAX_QUERY_RESIDUES)) == MAX_QUERY_RESIDUES


# ------------------------------------------------------------ submit model


def test_submit_request_requires_exactly_one_query_source() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        BlastSubmitRequest()
    with pytest.raises(ValidationError, match="exactly one"):
        BlastSubmitRequest(protein_id=UID, sequence="MALR")


@pytest.mark.parametrize(
    ("program", "expected"),
    [("blastp", "protein"), ("tblastn", "protein"), ("blastn", "dna"), ("blastx", "dna")],
)
def test_query_type_follows_the_program(program: str, expected: str) -> None:
    """`stype` describes the QUERY, not the database.

    tblastn searches a nucleotide database with a protein query, so it is
    "protein"; blastx is the mirror image. Getting these backwards makes EBI
    reject every submission for two of the four programs.
    """
    request = BlastSubmitRequest(sequence="MALR", program=program)
    assert request.query_type == expected


def test_submit_request_rejects_a_hostile_database_name() -> None:
    with pytest.raises(ValidationError, match="EBI database name"):
        BlastSubmitRequest(sequence="MALR", database="../../etc/passwd")


def test_submit_request_rejects_a_non_numeric_expect_threshold() -> None:
    with pytest.raises(ValidationError, match="must be a number"):
        BlastSubmitRequest(sequence="MALR", exp="soon")


def test_submit_request_rejects_a_non_positive_expect_threshold() -> None:
    with pytest.raises(ValidationError, match="greater than zero"):
        BlastSubmitRequest(sequence="MALR", exp="0")


def test_submit_request_normalises_matrix_and_database_case() -> None:
    request = BlastSubmitRequest(sequence="MALR", database="UniProtKB", matrix="blosum62")
    assert request.database == "uniprotkb"
    assert request.matrix == "BLOSUM62"


# ----------------------------------------------------------------- job ids


@pytest.mark.parametrize("bad", ["../../secret", "job id", "a/b", ""])
def test_validate_job_id_rejects_path_and_space_characters(bad: str) -> None:
    """The job id is interpolated into a URL path — an unchecked one is an SSRF hole."""
    with pytest.raises(SourceNotFoundError):
        validate_job_id(bad)


def test_validate_job_id_accepts_a_real_ebi_job_id() -> None:
    assert validate_job_id(f"  {JOB_ID}  ") == JOB_ID


# ------------------------------------------------------------------ email


def test_contact_email_defaults_to_a_non_personal_address(monkeypatch) -> None:
    monkeypatch.delenv("BLAST_CONTACT_EMAIL", raising=False)
    assert contact_email() == DEFAULT_CONTACT_EMAIL


def test_contact_email_reads_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("BLAST_CONTACT_EMAIL", "lab@example.org")
    assert contact_email() == "lab@example.org"


def test_blank_environment_value_falls_back_to_the_default(monkeypatch) -> None:
    monkeypatch.setenv("BLAST_CONTACT_EMAIL", "   ")
    assert contact_email() == DEFAULT_CONTACT_EMAIL


# --------------------------------------------------------------- transport


@respx.mock
async def test_submit_posts_a_form_body_ebi_understands() -> None:
    route = respx.post(RUN_URL).mock(return_value=httpx.Response(200, text=JOB_ID))
    job_id = await EBIBlastClient().submit(
        sequence="MALRKGG",
        program="blastp",
        database="uniprotkb",
        stype="protein",
        exp="1e-3",
        alignments=50,
        scores=50,
        matrix="BLOSUM62",
        filter_low_complexity=False,
    )
    assert job_id == JOB_ID
    body = dict(
        pair.split("=", 1) for pair in route.calls[0].request.content.decode().split("&")
    )
    assert body["program"] == "blastp"
    assert body["stype"] == "protein"
    assert body["database"] == "uniprotkb"
    assert body["sequence"] == "MALRKGG"
    assert body["filter"] == "F"
    assert body["exp"] == "1e-3"
    # EBI rejects a submission with no contact address outright.
    assert "email" in body and body["email"]


@respx.mock
async def test_submit_omits_optional_parameters_that_were_not_set() -> None:
    """A `matrix=None` must not be posted as the literal string "None"."""
    route = respx.post(RUN_URL).mock(return_value=httpx.Response(200, text=JOB_ID))
    await EBIBlastClient().submit(sequence="MALR", program="blastp", database="uniprotkb")
    body = route.calls[0].request.content.decode()
    assert "matrix" not in body
    assert "exp" not in body
    assert "filter" not in body


@respx.mock
async def test_submit_sets_filter_true_when_masking_is_requested() -> None:
    route = respx.post(RUN_URL).mock(return_value=httpx.Response(200, text=JOB_ID))
    await EBIBlastClient().submit(
        sequence="MALR",
        program="blastp",
        database="uniprotkb",
        filter_low_complexity=True,
    )
    assert "filter=T" in route.calls[0].request.content.decode()


@respx.mock
async def test_submit_maps_400_to_a_rejection_not_an_outage() -> None:
    """A 400 means the parameters are wrong; retrying them is pointless."""
    respx.post(RUN_URL).mock(
        return_value=httpx.Response(400, text="Sequence type is not compatible")
    )
    with pytest.raises(BlastRequestRejected, match="not compatible"):
        await EBIBlastClient().submit(
            sequence="MALR", program="blastp", database="uniprotkb"
        )


@respx.mock
async def test_submit_maps_5xx_to_unavailable() -> None:
    respx.post(RUN_URL).mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(SourceUnavailableError):
        await EBIBlastClient().submit(
            sequence="MALR", program="blastp", database="uniprotkb"
        )


@respx.mock
async def test_submit_rejects_a_body_that_is_not_a_job_id() -> None:
    """EBI has served HTML error pages with a 200 before. A 200 is not a job."""
    respx.post(RUN_URL).mock(return_value=httpx.Response(200, text="<html>oops</html>"))
    with pytest.raises(SourceUnavailableError, match="no usable job id"):
        await EBIBlastClient().submit(
            sequence="MALR", program="blastp", database="uniprotkb"
        )


@respx.mock
async def test_status_returns_the_bare_upstream_token() -> None:
    respx.get(STATUS_URL).mock(return_value=httpx.Response(200, text="running\n"))
    assert await EBIBlastClient().status(JOB_ID) == "RUNNING"


@respx.mock
async def test_status_404_reads_as_not_found_rather_than_an_outage() -> None:
    """EBI expires jobs. A 404 means "gone", and gone is a real answer."""
    respx.get(STATUS_URL).mock(return_value=httpx.Response(404))
    assert await EBIBlastClient().status(JOB_ID) == "NOT_FOUND"


@respx.mock
async def test_status_5xx_raises_unavailable() -> None:
    respx.get(STATUS_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(SourceUnavailableError):
        await EBIBlastClient().status(JOB_ID)


@respx.mock
async def test_retrieve_json_returns_the_parsed_payload() -> None:
    respx.get(RESULT_URL).mock(return_value=httpx.Response(200, json=blastp_payload()))
    body = await EBIBlastClient().retrieve_json(JOB_ID)
    assert body["program"] == "blastp"
    assert len(body["hits"]) == 6


@respx.mock
async def test_retrieve_json_404_is_an_expired_job() -> None:
    respx.get(RESULT_URL).mock(return_value=httpx.Response(404))
    with pytest.raises(SourceNotFoundError, match="expired"):
        await EBIBlastClient().retrieve_json(JOB_ID)


@respx.mock
async def test_retrieve_json_rejects_a_non_json_body() -> None:
    respx.get(RESULT_URL).mock(return_value=httpx.Response(200, text="not json"))
    with pytest.raises(SourceUnavailableError, match="non-JSON"):
        await EBIBlastClient().retrieve_json(JOB_ID)


@respx.mock
async def test_result_types_lists_identifiers() -> None:
    respx.get(TYPES_URL).mock(
        return_value=httpx.Response(
            200,
            json={"types": [{"identifier": "out"}, {"identifier": "json"}, {"nope": 1}]},
        )
    )
    assert await EBIBlastClient().result_types(JOB_ID) == ["out", "json"]
