"""P8 — the job registry, the polling policy, and the result projection.

The policy is the interesting part: `GET /api/blast/{job_id}` must answer fast
however slow the search is, must never hammer EBI, and must fetch the result
exactly once. Each of those is pinned by its own test here.

All upstream calls are mocked with respx. Nothing reaches the network.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.models.blast import BlastResult
from app.services.blast import BASE_URL, EBIBlastClient
from app.services.blast_jobs import (
    BlastJobRegistry,
    _normalise_status,
    parse_result,
)
from tests.helpers import load_json

JOB_ID = "ncbiblast-R20191128-094014-0332-71107816-p1m"
STATUS_URL = f"{BASE_URL}/status/{JOB_ID}"
RESULT_URL = f"{BASE_URL}/result/{JOB_ID}/json"


def payload() -> dict:
    return load_json("ebi_ncbiblast_result_P35858.json")


def new_registry(**kwargs: object) -> BlastJobRegistry:
    kwargs.setdefault("min_upstream_poll_seconds", 0.0)
    return BlastJobRegistry(EBIBlastClient(), **kwargs)  # type: ignore[arg-type]


def register(registry: BlastJobRegistry):
    return registry.register(
        JOB_ID,
        program="blastp",
        database="uniprotkb",
        query_length=605,
        query_source="P35858 chain A",
    )


# ------------------------------------------------------------- projection


def test_parse_result_reads_the_recorded_response_header() -> None:
    result = parse_result(payload())
    assert result.program == "blastp"
    assert result.version == "BLASTP 2.9.0+"
    assert result.query_id == "ALS_HUMAN"
    assert result.query_length == 605
    assert result.databases == ["uniprotkb_swissprot"]
    assert result.started_at == "2019-11-28T09:40:14+00:00"


def test_parse_result_projects_every_hit() -> None:
    result = parse_result(payload())
    assert result.hit_count == 6
    assert len(result.hits) == 6
    assert [h.accession for h in result.hits] == [
        "P35858",
        "O02833",
        "P35859",
        "P70389",
        "Q8R5M3",
        "Q80X72",
    ]


def test_parse_result_carries_the_fields_the_results_table_renders() -> None:
    top = parse_result(payload()).hits[0]
    assert top.rank == 1
    assert top.entry_id == "ALS_HUMAN"
    assert top.organism == "Homo sapiens"
    assert top.gene == "IGFALS"
    assert top.length == 605
    assert top.identity_percent == 100.0
    assert top.expect == 0.0
    assert top.score == 3142
    assert top.bit_score == 1214.91
    assert top.database == "SP"


def test_hit_description_prefers_the_clean_uniprot_name() -> None:
    """`hit_desc` appends OS=/OX=/GN= noise; `hit_uni_de` is the name alone."""
    top = parse_result(payload()).hits[0]
    assert top.description == (
        "Insulin-like growth factor-binding protein complex acid labile subunit"
    )
    assert "OS=" not in (top.description or "")


def test_hit_summary_uses_the_best_hsp_not_the_first_one() -> None:
    """EBI orders HSPs by score today. We must not depend on that.

    Hit 5 in the recording has three HSPs (527 / 462 / 454). Reversing them
    must not change the reported identity — a table quietly showing the weakest
    alignment would be nearly impossible to spot from the outside.
    """
    original = payload()
    forward = parse_result(original).hits[4]

    reversed_payload = payload()
    reversed_payload["hits"][4]["hit_hsps"].reverse()
    backward = parse_result(reversed_payload).hits[4]

    assert forward.score == 527
    assert backward.score == forward.score
    assert backward.identity_percent == forward.identity_percent
    assert backward.expect == forward.expect


def test_every_hsp_is_kept_even_though_only_the_best_is_summarised() -> None:
    hit = parse_result(payload()).hits[4]
    assert len(hit.hsps) == 3
    assert [h.rank for h in hit.hsps] == [1, 2, 3]
    assert hit.hsps[0].query_start is not None and hit.hsps[0].query_end is not None


def test_uniprot_accession_is_set_for_importable_hits() -> None:
    hits = parse_result(payload()).hits
    assert all(h.uniprot_accession == h.accession for h in hits)


def test_non_uniprot_accessions_get_no_import_link() -> None:
    """A nucleotide hit carries an ENA id the import flow has no client for.

    Returning None is what stops the UI offering an Open button that can only
    fail.
    """
    body = payload()
    body["hits"] = [dict(body["hits"][0], hit_acc="AL021546", hit_db="EM_REL")]
    hit = parse_result(body).hits[0]
    assert hit.accession == "AL021546"
    assert hit.uniprot_accession is None


def test_parse_result_survives_a_payload_with_no_hits() -> None:
    result = parse_result({"program": "blastp", "hits": []})
    assert result.hit_count == 0
    assert result.hits == []


def test_parse_result_survives_junk_where_lists_were_expected() -> None:
    """A partial upstream payload must degrade, not raise."""
    result = parse_result({"hits": "nope", "dbs": 7, "query_len": "not a number"})
    assert isinstance(result, BlastResult)
    assert result.hit_count == 0
    assert result.databases == []
    assert result.query_length is None


def test_hit_rank_falls_back_to_position_when_upstream_omits_it() -> None:
    body = payload()
    for hit in body["hits"]:
        hit.pop("hit_num", None)
    ranks = [h.rank for h in parse_result(body).hits]
    assert ranks == [1, 2, 3, 4, 5, 6]


# ------------------------------------------------------------ status words


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("RUNNING", "RUNNING"),
        ("finished", "FINISHED"),
        (" QUEUED ", "QUEUED"),
        ("FAILURE", "FAILURE"),
        ("NOT_FOUND", "NOT_FOUND"),
        ("SOMETHING_NEW", "ERROR"),
    ],
)
def test_unknown_upstream_status_words_become_errors(raw: str, expected: str) -> None:
    assert _normalise_status(raw) == expected


# ----------------------------------------------------------------- policy


async def test_poll_returns_none_for_a_job_this_process_never_registered() -> None:
    assert await new_registry().poll("ncbiblast-nope") is None


@respx.mock
async def test_poll_advances_a_running_job() -> None:
    registry = new_registry()
    register(registry)
    respx.get(STATUS_URL).mock(return_value=httpx.Response(200, text="RUNNING"))

    record = await registry.poll(JOB_ID)
    assert record is not None
    assert record.status == "RUNNING"
    assert record.finished is False
    assert record.result is None
    assert record.poll_count == 1


@respx.mock
async def test_poll_downloads_the_result_when_the_job_finishes() -> None:
    registry = new_registry()
    register(registry)
    respx.get(STATUS_URL).mock(return_value=httpx.Response(200, text="FINISHED"))
    result_route = respx.get(RESULT_URL).mock(
        return_value=httpx.Response(200, json=payload())
    )

    record = await registry.poll(JOB_ID)
    assert record is not None
    assert record.status == "FINISHED"
    assert record.finished is True
    assert record.result is not None
    assert record.result.hit_count == 6
    assert "6 hits" in record.message
    assert result_route.call_count == 1


@respx.mock
async def test_a_terminal_job_is_answered_from_memory_with_no_upstream_call() -> None:
    """Rule 1. A browser left polling a finished job costs EBI nothing."""
    registry = new_registry()
    register(registry)
    status_route = respx.get(STATUS_URL).mock(
        return_value=httpx.Response(200, text="FINISHED")
    )
    result_route = respx.get(RESULT_URL).mock(
        return_value=httpx.Response(200, json=payload())
    )

    await registry.poll(JOB_ID)
    for _ in range(5):
        record = await registry.poll(JOB_ID)

    assert status_route.call_count == 1
    assert result_route.call_count == 1
    assert record is not None and record.poll_count == 1


@respx.mock
async def test_upstream_polls_are_throttled_however_fast_the_client_asks() -> None:
    """Rule 2, tested with the throttle actually on (the suite default is off).

    A browser polling every 500 ms must not turn into 120 requests/minute at
    EBI — but it still gets an answer every time it asks.
    """
    registry = BlastJobRegistry(EBIBlastClient(), min_upstream_poll_seconds=60.0)
    register(registry)
    status_route = respx.get(STATUS_URL).mock(
        return_value=httpx.Response(200, text="RUNNING")
    )

    records = [await registry.poll(JOB_ID) for _ in range(4)]

    assert status_route.call_count == 1
    assert all(r is not None and r.status == "RUNNING" for r in records)


@respx.mock
async def test_a_transport_blip_does_not_fail_the_job() -> None:
    """A 503 while checking status means "ask again", not "the search failed"."""
    registry = new_registry()
    register(registry)
    respx.get(STATUS_URL).mock(return_value=httpx.Response(503))

    record = await registry.poll(JOB_ID)
    assert record is not None
    assert record.status == "QUEUED"
    assert record.finished is False
    assert "Could not reach EBI" in record.message


@respx.mock
async def test_an_expired_job_becomes_not_found() -> None:
    registry = new_registry()
    register(registry)
    respx.get(STATUS_URL).mock(return_value=httpx.Response(404))

    record = await registry.poll(JOB_ID)
    assert record is not None
    assert record.status == "NOT_FOUND"
    assert record.finished is True


@respx.mock
async def test_a_failed_search_is_terminal_and_says_so() -> None:
    registry = new_registry()
    register(registry)
    respx.get(STATUS_URL).mock(return_value=httpx.Response(200, text="FAILURE"))

    record = await registry.poll(JOB_ID)
    assert record is not None
    assert record.status == "FAILURE"
    assert record.finished is True
    assert record.result is None


@respx.mock
async def test_a_finished_job_whose_download_fails_is_retried_not_lost() -> None:
    """The search succeeded; only the download did not. Losing it would be wrong."""
    registry = new_registry()
    register(registry)
    respx.get(STATUS_URL).mock(return_value=httpx.Response(200, text="FINISHED"))
    # 500, not 503: 503 is in `RETRYABLE_STATUS_CODES`, so `RetryingTransport`
    # would swallow it inside the first call and this test would be exercising
    # the retry transport instead of the poll-again policy it is here to pin.
    result_route = respx.get(RESULT_URL).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(200, json=payload()),
        ]
    )

    first = await registry.poll(JOB_ID)
    assert first is not None
    assert first.finished is False
    assert first.result is None
    assert "could not be downloaded" in first.message

    second = await registry.poll(JOB_ID)
    assert second is not None
    assert second.status == "FINISHED"
    assert second.result is not None
    assert result_route.call_count == 2


async def test_registry_reports_its_size_and_clears() -> None:
    registry = new_registry()
    register(registry)
    assert registry.size() == 1
    assert registry.get(JOB_ID) is not None
    registry.clear()
    assert registry.size() == 0
    assert registry.get(JOB_ID) is None


async def test_elapsed_seconds_is_reported_so_the_ui_can_show_real_progress() -> None:
    registry = new_registry()
    record = register(registry)
    status = record.to_status()
    assert status.elapsed_seconds >= 0.0
    assert status.query_source == "P35858 chain A"
    assert status.query_length == 605
