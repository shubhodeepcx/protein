from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

import httpx

logger = logging.getLogger(__name__)

# Exponential backoff: 0.5s, 1s, 2s -- three retries on top of the first attempt.
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 0.5

# 429 (rate limited) and 5xx are the upstream's own "try again" signal; any
# other status is a real answer and must not be retried.
RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})

# Per-host cap on simultaneous in-flight requests. Keeps every client polite
# to its upstream even when a caller fans out (e.g. RCSB search enrichment),
# without callers having to know this transport exists.
DEFAULT_MAX_CONCURRENT_PER_HOST = 6

_host_semaphores: dict[str, asyncio.Semaphore] = defaultdict(
    lambda: asyncio.Semaphore(DEFAULT_MAX_CONCURRENT_PER_HOST)
)


async def _sleep(seconds: float) -> None:
    """Indirection so tests can patch `app.services.resilience._sleep` instead
    of the real `asyncio.sleep`, which would also stall pytest-asyncio itself."""
    await asyncio.sleep(seconds)


class RetryingTransport(httpx.AsyncBaseTransport):
    """Wraps an `httpx` transport with retry/backoff and a per-host concurrency cap.

    Applied once in `external.new_client()` so every outbound client (RCSB,
    AlphaFold, UniProt) gets both behaviours without touching call sites.
    """

    def __init__(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
    ) -> None:
        self._transport = transport or httpx.AsyncHTTPTransport()
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        semaphore = _host_semaphores[request.url.host]
        async with semaphore:
            attempt = 0
            while True:
                try:
                    response = await self._transport.handle_async_request(request)
                except httpx.TransportError:
                    if attempt >= self._max_retries:
                        raise
                    await self._backoff(request, attempt)
                    attempt += 1
                    continue

                if (
                    response.status_code not in RETRYABLE_STATUS_CODES
                    or attempt >= self._max_retries
                ):
                    return response

                await response.aclose()
                await self._backoff(request, attempt)
                attempt += 1

    async def _backoff(self, request: httpx.Request, attempt: int) -> None:
        logger.warning(
            "Retrying %s %s (attempt %d/%d) after a transient failure",
            request.method,
            request.url,
            attempt + 1,
            self._max_retries,
        )
        await _sleep(self._backoff_base_seconds * (2**attempt))

    async def aclose(self) -> None:
        await self._transport.aclose()
