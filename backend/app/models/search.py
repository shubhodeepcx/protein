from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# The three external databases P5 can search. `SourceFilter` adds "all" for the
# query-string filter on GET /api/search.
SourceName = Literal["rcsb", "alphafold", "uniprot"]
SourceFilter = Literal["all", "rcsb", "alphafold", "uniprot"]

ALL_SOURCES: tuple[SourceName, ...] = ("rcsb", "alphafold", "uniprot")


class SearchResult(BaseModel):
    """One hit from an external protein database.

    The first five fields are the uniform contract every source must fill in
    (`title`/`organism`/`description` may legitimately be null). Everything
    below them is best-effort and source-dependent — a field is only populated
    when that database actually publishes it.
    """

    source: SourceName = Field(..., description="Database the hit came from.")
    source_id: str = Field(..., description="PDB ID or UniProt accession.")
    title: str | None = Field(None, description="Human-readable structure or protein name.")
    organism: str | None = Field(None, description="Source organism, scientific name.")
    description: str | None = Field(None, description="Short descriptive blurb.")

    # Source-dependent extras.
    resolution: float | None = Field(
        None, description="Refinement resolution in angstroms (RCSB X-ray/EM entries)."
    )
    method: str | None = Field(
        None, description="Experimental or predictive method, e.g. 'X-RAY DIFFRACTION'."
    )
    release_year: int | None = Field(None, description="Year the entry was first released.")
    sequence_length: int | None = Field(None, description="Residue count of the sequence.")
    confidence: float | None = Field(
        None, description="Mean pLDDT for AlphaFold predictions, 0-100."
    )


class SearchResponse(BaseModel):
    """Merged, deduped fan-out response for GET /api/search."""

    query: str = Field(..., description="The normalised query that was executed.")
    results: list[SearchResult] = Field(..., description="Merged hits across all queried sources.")
    failed_sources: list[SourceName] = Field(
        ..., description="Sources that raised — their hits are missing from `results`."
    )


class ImportRequest(BaseModel):
    """Body for POST /api/proteins/import."""

    source: SourceName = Field(..., description="Database to import from.")
    source_id: str = Field(
        ..., min_length=1, max_length=64, description="PDB ID or UniProt accession to import."
    )
