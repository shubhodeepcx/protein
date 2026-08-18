from __future__ import annotations

from typing import Any

import httpx

from app.models.search import SearchResult

# AGENTS.md section 3 / spec 5.4: every external call gets an explicit 10s timeout.
EXTERNAL_TIMEOUT_SECONDS = 10.0

# Spec 5.4 caps nothing explicitly; the brief asks for a sane per-source cap.
# 25 bounds the fan-out cost (RCSB enriches each hit with a metadata call), and
# anything dropped is logged rather than silently discarded.
MAX_RESULTS_PER_SOURCE = 25

# Politeness header — EBI and UniProt both ask API consumers to identify themselves.
USER_AGENT = "ProteoLens/0.1 (+https://github.com/shubhodeepcx/protein)"

# Normalised, source-agnostic metadata dict. Keys that match `SearchResult`
# field names are promoted into the API model by `to_search_result`; anything
# else (file URLs, cross-references) stays internal to the service layer.
Metadata = dict[str, Any]


class ExternalSourceError(RuntimeError):
    """Base class for every failure raised by an external database client."""


class SourceNotFoundError(ExternalSourceError):
    """The source has no entry/model for the requested identifier (-> HTTP 404)."""


class SourceUnavailableError(ExternalSourceError):
    """The source could not be reached or returned an unusable response (-> HTTP 502)."""


def new_client(**kwargs: Any) -> httpx.AsyncClient:
    """An httpx.AsyncClient preconfigured with the project's timeout and UA."""
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    return httpx.AsyncClient(
        timeout=EXTERNAL_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers=headers,
        **kwargs,
    )


def to_search_result(meta: Metadata) -> SearchResult:
    """Project a normalised metadata dict onto the API-facing SearchResult model."""
    fields = SearchResult.model_fields
    return SearchResult.model_validate({k: v for k, v in meta.items() if k in fields})


def as_float(value: object) -> float | None:
    """Coerce an untrusted JSON scalar to float, or None when it is not numeric."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def as_int(value: object) -> int | None:
    """Coerce an untrusted JSON scalar to int, or None when it is not numeric."""
    f = as_float(value)
    return None if f is None else int(f)


def year_from_iso(value: object) -> int | None:
    """Pull the 4-digit year out of an ISO-8601 date string like '1981-07-28T00:00:00Z'."""
    if not isinstance(value, str) or len(value) < 4:
        return None
    return as_int(value[:4])
