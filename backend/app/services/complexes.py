"""EBI Complex Portal client and projection onto `ProteinComplexes` (P9).

Two halves, deliberately separated the same way `services/annotations.py` splits
P6:

* `ComplexPortalClient` does the I/O — one GET, cached, with the project's
  standard timeout / retry transport from `services/external.py`.
* `build_complexes` is pure — a recorded Complex Portal response in, a Pydantic
  model out. That is what makes the projection testable entirely offline.

Three things about the real service shaped this module, all verified against
the live API rather than assumed:

1. **`/search/{query}` already carries the participants.** Each element in the
   response embeds the full interactor list with stoichiometry, so the
   participant table costs one request, not one request per complex. The
   `/details/{ac}` endpoint the brief pointed at is keyed by IntAct `EBI-*`
   accessions, not `CPX-*` ones; `/complex-simplified/{CPX}` returns exactly
   the element shape `/search` already gave us. Neither adds anything, so
   neither is called.
2. **The search is full text, so it over-matches.** Querying `P01308` returns
   nine complexes, and two of them — the insulin receptor complexes — merely
   name "Insulin (P01308)" in their curated description while containing no
   insulin at all. Reporting those as complexes containing insulin would be
   wrong biology, so a complex is kept only when the protein is an actual
   participant. `search_matches` still reports the raw upstream count, so the
   difference is visible rather than silently swallowed.
3. **Complex Portal indexes base accessions only.** `search/P01308-1` returns
   zero results where `search/P01308` returns nine, so an isoform accession is
   reduced to its base before it is sent, and matched at base level too.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from app.models.complexes import ComplexParticipant, ProteinComplex, ProteinComplexes
from app.services.cache import TTLCache
from app.services.external import (
    Metadata,
    SourceNotFoundError,
    SourceUnavailableError,
    as_int,
    new_client,
)

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.ebi.ac.uk/intact/complex-ws/search/{query}"
COMPLEX_URL = "https://www.ebi.ac.uk/complexportal/complex/{accession}"

# A runaway bound, NOT a display cap. `/search/*` returns the entire 20,000+
# complex corpus in a single response, so a query that somehow degenerated into
# a wildcard would otherwise hand us a multi-megabyte body to parse and cache.
# The largest number of complexes observed for any single accession is under
# 30, so this can only ever fire on a bug — and when it does, the response
# still reports `search_matches` from upstream and the shortfall is logged.
MAX_COMPLEXES_PER_QUERY = 500

# "minValue: 0, maxValue: 1" — the only shape the service emits, verified over a
# 2,500-complex sample. Absent stoichiometry arrives as JSON null, not as text.
_STOICHIOMETRY_RE = re.compile(r"minValue:\s*(-?\d+)\s*,\s*maxValue:\s*(-?\d+)")

# Only these schemes may reach an `<a href>`. Upstream link fields are data
# from a third party, and a `javascript:` URL in one would be an XSS vector.
_SAFE_SCHEMES = ("https", "http")


class ComplexPortalClient:
    """Async client for the EBI Complex Portal web service."""

    source = "complex-portal"

    def __init__(self, cache: TTLCache[Metadata] | None = None) -> None:
        # Cached for the same reason UniProt annotations are: complexes change
        # on a curation cadence, not per request, and the panel refetches on
        # every tab open.
        self._cache: TTLCache[Metadata] = cache if cache is not None else TTLCache()

    async def search_by_accession(self, accession: str) -> Metadata:
        """The raw Complex Portal search body for one UniProt accession.

        Returned unprojected on purpose: `build_complexes` owns the mapping, so
        that mapping stays a pure function over recorded JSON.
        """
        query = base_accession(accession)
        cached = self._cache.get(query)
        if cached is not None:
            return cached

        url = SEARCH_URL.format(query=quote(query, safe=""))
        params = {"first": 0, "number": MAX_COMPLEXES_PER_QUERY}
        async with new_client(headers={"Accept": "application/json"}) as client:
            try:
                response = await client.get(url, params=params)
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(
                    f"Complex Portal request failed: {exc}"
                ) from exc

        if response.status_code == 404:
            raise SourceNotFoundError(f"Complex Portal has no index for {query}")
        if response.status_code >= 400:
            raise SourceUnavailableError(
                f"Complex Portal search for {query} returned HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise SourceUnavailableError(
                "Complex Portal returned a non-JSON body"
            ) from exc
        if not isinstance(body, dict):
            raise SourceUnavailableError(
                "Complex Portal returned an unexpected payload"
            )

        self._cache.put(query, body)
        return body


# --------------------------------------------------------------- projection


def build_complexes(
    uid: str,
    body: Metadata,
    *,
    accession: str,
    note: str,
) -> ProteinComplexes:
    """Flatten a Complex Portal search response into the API payload. Pure."""
    query = base_accession(accession)
    elements = body.get("elements")
    elements = elements if isinstance(elements, list) else []

    total = as_int(body.get("totalNumberOfResults"))
    if total is None:
        total = len(elements)
    if total > len(elements):
        # Only reachable if the runaway bound fired. Never silent.
        logger.warning(
            "Complex Portal reported %d matches for %s but returned %d",
            total,
            query,
            len(elements),
        )

    complexes: list[ProteinComplex] = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        built = _complex(element, query=query)
        # Full-text over-match: the accession appears in the prose, not in the
        # participant list. Dropping it is the whole point; `search_matches`
        # keeps the count honest.
        if built is None:
            continue
        complexes.append(built)

    if len(complexes) < len(elements):
        logger.info(
            "Complex Portal matched %d records for %s; %d contain it as a participant",
            len(elements),
            query,
            len(complexes),
        )

    # Curated complexes first, upstream order preserved within each group.
    # A predicted complex is a computational inference with no curated function
    # text, so it is the weaker answer to "which complex is this protein in?"
    # and must not outrank a curated one just because Solr scored it higher.
    # Sorting here rather than in the panel keeps the selector and the list in
    # agreement by construction.
    complexes.sort(key=lambda c: c.predicted)

    return ProteinComplexes(
        id=uid,
        accession=accession,
        accession_resolved=True,
        resolution_note=note,
        query=query,
        complexes=complexes,
        search_matches=total,
    )


def empty_complexes(
    uid: str,
    note: str,
    accession: str | None = None,
    query: str | None = None,
) -> ProteinComplexes:
    """A valid, entirely empty payload — the panel explains itself instead."""
    return ProteinComplexes(
        id=uid,
        accession=accession,
        accession_resolved=False,
        resolution_note=note,
        query=query,
    )


def base_accession(accession: str) -> str:
    """Strip an isoform / PRO-chain suffix: 'P01308-1' -> 'P01308'.

    Complex Portal indexes base accessions, so the suffixed form finds nothing
    (`search/P01308-1` is empty where `search/P01308` returns nine complexes).
    The same reduction is applied to participant identifiers, so a complex
    containing the PRO chain `P06213-PRO_0000016689` matches a query for
    `P06213`.
    """
    return accession.strip().upper().split("-", 1)[0]


# ------------------------------------------------------------------ helpers


def _complex(element: dict[str, object], *, query: str) -> ProteinComplex | None:
    """One search element, or None when it does not contain the query protein."""
    accession = _text(element.get("complexAC"))
    if not accession:
        return None

    participants: list[ComplexParticipant] = []
    contains_query = False
    for raw in element.get("interactors") or []:
        if not isinstance(raw, dict):
            continue
        participant = _participant(raw, query=query)
        if participant is None:
            continue
        contains_query = contains_query or participant.is_query_protein
        participants.append(participant)

    if not contains_query:
        return None

    return ProteinComplex(
        accession=accession,
        name=_text(element.get("complexName")) or "",
        organism=_organism(element.get("organismName")),
        description=_text(element.get("description")),
        predicted=element.get("predictedComplex") is True,
        url=COMPLEX_URL.format(accession=quote(accession, safe="")),
        participants=participants,
    )


def _participant(raw: dict[str, object], *, query: str) -> ComplexParticipant | None:
    identifier = _text(raw.get("identifier"))
    if not identifier:
        return None
    minimum, maximum = _stoichiometry(raw.get("stochiometry"))
    return ComplexParticipant(
        identifier=identifier,
        name=_text(raw.get("name")) or "",
        description=_text(raw.get("description")),
        interactor_type=_text(raw.get("interactorType")),
        organism=_organism(raw.get("organismName")),
        stoichiometry=_format_stoichiometry(minimum, maximum),
        stoichiometry_min=minimum,
        stoichiometry_max=maximum,
        url=_safe_url(raw.get("identifierLink")),
        is_query_protein=base_accession(identifier) == query,
    )


def _stoichiometry(value: object) -> tuple[int | None, int | None]:
    """Parse 'minValue: 0, maxValue: 1'. Absent stoichiometry is JSON null."""
    if not isinstance(value, str):
        return None, None
    match = _STOICHIOMETRY_RE.search(value)
    if match is None:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _format_stoichiometry(minimum: int | None, maximum: int | None) -> str | None:
    """'2' for a fixed copy number, '0-1' for an optional participant."""
    if minimum is None and maximum is None:
        return None
    if minimum is None or maximum is None:
        return str(minimum if minimum is not None else maximum)
    if minimum == maximum:
        return str(minimum)
    return f"{minimum}-{maximum}"


def _organism(value: object) -> str | None:
    """'Homo sapiens; 9606' -> 'Homo sapiens'.

    Complex Portal appends the taxon id to the scientific name in one string;
    the rest of this codebase carries a bare scientific name.
    """
    text = _text(value)
    if text is None:
        return None
    return text.split(";", 1)[0].strip() or None


def _safe_url(value: object) -> str | None:
    """An upstream link, upgraded to https, or None if it is not http(s).

    Complex Portal ships its ChEBI links as plain `http://`, which both hosts
    redirect anyway. Anything that is not http(s) is dropped rather than
    rendered: these strings end up in an `<a href>`, and a `javascript:` URL
    from a third-party feed is an XSS vector, not a link.
    """
    text = _text(value)
    if text is None:
        return None
    parts = urlsplit(text)
    if parts.scheme not in _SAFE_SCHEMES or not parts.netloc:
        logger.info("Dropped a Complex Portal link with scheme %r", parts.scheme)
        return None
    return urlunsplit(("https", parts.netloc, parts.path, parts.query, parts.fragment))


def _text(value: object) -> str | None:
    """A non-empty stripped string, or None. Untrusted JSON in, str|None out."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


# ------------------------------------------------------------- the singleton

# Module-level, for the same reason `api/search.py` holds its clients that way:
# the TTL cache is supposed to survive between requests. It is deliberately not
# in `search.py`'s `_CLIENTS` registry — that dict is typed to the uniform
# three-coroutine `SourceClient` contract, and Complex Portal hosts no
# structures to download and is not a search source.
_CLIENT = ComplexPortalClient()


def get_complex_portal_client() -> ComplexPortalClient:
    """The Complex Portal singleton. Read through, so tests can swap it."""
    return _CLIENT
