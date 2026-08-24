"""Project UniRef cluster data onto `SimilarProteinsResponse` (P8).

Same split as `services/annotations.py`, for the same reason:

* `build_similar_proteins` is pure — recorded UniRef payloads in, a Pydantic
  model out, no I/O. That is what makes the field mapping testable offline.
* the I/O lives on `UniProtClient` (`find_uniref_cluster`,
  `fetch_uniref_members`), because UniRef is served from the same host under
  the same politeness budget as everything else UniProt.

Accession resolution is *reused* from `services/annotations.py` rather than
reimplemented: "which UniProt entry is this local structure?" is one question,
and two answers to it that could drift apart would be a bug waiting to happen.
"""

from __future__ import annotations

import logging

from app.models.similarity import (
    DEFAULT_UNIREF_IDENTITY,
    SimilarProtein,
    SimilarProteinsResponse,
)
from app.services.external import Metadata, as_int

logger = logging.getLogger(__name__)

UNIPROT_ENTRY_URL = "https://www.uniprot.org/uniprotkb/{accession}/entry"


def empty_similar(
    uid: str,
    note: str,
    *,
    accession: str | None = None,
    identity: float = DEFAULT_UNIREF_IDENTITY,
) -> SimilarProteinsResponse:
    """A successful, empty answer. Not an error — see the model docstring."""
    return SimilarProteinsResponse(
        id=uid,
        accession=accession,
        accession_resolved=accession is not None,
        resolution_note=note,
        identity_threshold=identity,
    )


def build_similar_proteins(
    uid: str,
    cluster: Metadata,
    members: list[Metadata],
    *,
    accession: str,
    note: str,
    identity: float = DEFAULT_UNIREF_IDENTITY,
) -> SimilarProteinsResponse:
    """Flatten a UniRef cluster + its member records into the API payload. Pure."""
    representative = cluster.get("representativeMember")
    representative_accession = _member_accession(
        representative if isinstance(representative, dict) else {}
    )

    projected: list[SimilarProtein] = []
    seen: set[str] = set()
    for raw in members:
        member_accession = _member_accession(raw)
        if not member_accession:
            continue
        # The query protein is not one of its own "similar proteins".
        if member_accession == accession:
            continue
        if member_accession in seen:
            continue
        seen.add(member_accession)
        projected.append(
            SimilarProtein(
                accession=member_accession,
                entry_id=_text(raw.get("memberId")),
                protein_name=_text(raw.get("proteinName")),
                organism=_text(raw.get("organismName")),
                taxon_id=as_int(raw.get("organismTaxId")),
                sequence_length=as_int(raw.get("sequenceLength")),
                is_representative=member_accession == representative_accession,
                uniprot_url=UNIPROT_ENTRY_URL.format(accession=member_accession),
            )
        )

    member_count = as_int(cluster.get("memberCount")) or 0
    # `members` is what UniRef returned for the page we asked for; the cluster
    # knows its own true size. Saying so beats silently implying the cluster is
    # only as big as the page.
    truncated = member_count > len(members)

    return SimilarProteinsResponse(
        id=uid,
        accession=accession,
        accession_resolved=True,
        resolution_note=note,
        identity_threshold=identity,
        cluster_id=_text(cluster.get("id")),
        cluster_name=_text(cluster.get("name")),
        member_count=member_count,
        organism_count=as_int(cluster.get("organismCount")) or 0,
        members=projected,
        truncated=truncated,
    )


def _member_accession(member: Metadata) -> str | None:
    """A member's primary accession.

    UniRef lists every accession that maps to the member sequence; the first is
    the primary one, and the rest are secondary accessions for the same entry.
    """
    accessions = member.get("accessions")
    if isinstance(accessions, list):
        for value in accessions:
            if isinstance(value, str) and value.strip():
                return value.strip().upper()
    return None


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
