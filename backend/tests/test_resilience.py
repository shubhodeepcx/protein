"""Unit + wiring tests for `services/resilience.py`.

The unit tests drive `RetryingTransport` directly against a hand-scripted
inner transport, so the retry/backoff state machine is pinned without any
real network or real sleeping. One end-to-end test at the bottom proves the
transport is actually wired into `external.new_client()`, using respx against
a real client class the way `test_external_clients.py` does.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from app.services.external import new_client
from app.services.rcsb import RCSBClient
from app.services.resilience import RetryingTransport
from tests.helpers import load_json


def _request(url: str = "https://example.test/x") -> httpx.Request:
    return httpx.Request("GET", url)


class _ScriptedTransport(httpx.AsyncBaseTransport):
    """Returns/raises each entry of `script` in order, one per call."""

    def __init__(self, script: list[httpx.Response | Exception]) -> None:
        self._script = list(script)
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        step = self._script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


@pytest.fixture
def recorded_sleeps(monkeypatch):
    """Overrides the autouse no-op sleep so a test can assert delay values."""
    sleeps: list[float] = []

    async def record(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("app.services.resilience._sleep", record)
    return sleeps


# --------------------------------------------------------------- status retry


async def test_retries_a_retryable_status_then_succeeds(recorded_sleeps) -> None:
    inner = _ScriptedTransport([httpx.Response(503), httpx.Response(200)])

    response = await RetryingTransport(inner).handle_async_request(_request())

    assert response.status_code == 200
    assert inner.calls == 2
    assert recorded_sleeps == [0.5]


async def test_gives_up_and_returns_the_last_response_after_max_retries(
    recorded_sleeps,
) -> None:
    inner = _ScriptedTransport([httpx.Response(503)] * 4)  # 1 + 3 retries

    response = await RetryingTransport(inner).handle_async_request(_request())

    assert response.status_code == 503
    assert inner.calls == 4
    # Exponential: 0.5, 1.0, 2.0 -- the backoff base doubling each attempt.
    assert recorded_sleeps == [0.5, 1.0, 2.0]


async def test_does_not_retry_a_non_retryable_status(recorded_sleeps) -> None:
    # 404/500 are real answers, not "try again" signals -- a 500 in
    # particular could be an application bug upstream, not a blip.
    inner = _ScriptedTransport([httpx.Response(404)])

    response = await RetryingTransport(inner).handle_async_request(_request())

    assert response.status_code == 404
    assert inner.calls == 1
    assert recorded_sleeps == []


# ------------------------------------------------------------ transport error


async def test_retries_a_transport_error_then_succeeds(recorded_sleeps) -> None:
    inner = _ScriptedTransport([httpx.ConnectError("boom"), httpx.Response(200)])

    response = await RetryingTransport(inner).handle_async_request(_request())

    assert response.status_code == 200
    assert inner.calls == 2
    assert recorded_sleeps == [0.5]


async def test_reraises_a_transport_error_after_max_retries(recorded_sleeps) -> None:
    inner = _ScriptedTransport([httpx.ConnectError("boom")] * 4)

    with pytest.raises(httpx.ConnectError):
        await RetryingTransport(inner).handle_async_request(_request())

    assert inner.calls == 4
    assert recorded_sleeps == [0.5, 1.0, 2.0]


# --------------------------------------------------------- per-host concurrency


async def test_caps_concurrent_requests_to_the_same_host(monkeypatch) -> None:
    monkeypatch.setattr("app.services.resilience.DEFAULT_MAX_CONCURRENT_PER_HOST", 2)

    current = 0
    peak = 0
    lock = asyncio.Lock()

    class _SlowTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal current, peak
            async with lock:
                current += 1
                peak = max(peak, current)
            await asyncio.sleep(0.05)
            async with lock:
                current -= 1
            return httpx.Response(200)

    transport = RetryingTransport(_SlowTransport())
    host = "concurrency-cap.example.test"
    await asyncio.gather(
        *(
            transport.handle_async_request(httpx.Request("GET", f"https://{host}/{i}"))
            for i in range(6)
        )
    )

    assert peak == 2


# --------------------------------------------------------------------- wiring


def test_new_client_installs_the_retrying_transport() -> None:
    client = new_client()
    assert isinstance(client._transport, RetryingTransport)


@respx.mock
async def test_rcsb_search_survives_a_transient_502_via_the_shared_transport() -> None:
    """End-to-end: a real client (not a scripted transport) retries through
    the transport `new_client()` actually installs."""
    respx.post("https://search.rcsb.org/rcsbsearch/v2/query").mock(
        side_effect=[
            httpx.Response(502),
            httpx.Response(200, json=load_json("rcsb_search_insulin.json")),
        ]
    )
    respx.get(url__startswith="https://data.rcsb.org/rest/v1/core/entry/").mock(
        return_value=httpx.Response(200, json=load_json("rcsb_entry_1CRN.json"))
    )
    respx.get(url__startswith="https://data.rcsb.org/rest/v1/core/polymer_entity/").mock(
        return_value=httpx.Response(200, json=load_json("rcsb_polymer_entity_1CRN_1.json"))
    )

    results = await RCSBClient().search("insulin")

    assert [r.source_id for r in results] == ["1BOM", "2FHW"]
