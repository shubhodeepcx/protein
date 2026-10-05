from __future__ import annotations

import logging
from pathlib import Path

from Bio.PDB import MMCIFParser, PDBParser
from Bio.PDB.Structure import Structure
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.models.analytics import (
    AnalyticsResponse,
    ChainLength,
    CompositionEntry,
    HydrophobicityProfile,
    PropertyDistribution,
    SecondaryStructurePercentages,
)
from app.models.annotations import ProteinAnnotations
from app.models.complexes import ProteinComplexes
from app.models.compounds import CompoundsResponse
from app.models.functional import FunctionalRegions
from app.models.confidence import ConfidenceResponse
from app.models.protein import ProteinSummary
from app.models.similarity import DEFAULT_UNIREF_IDENTITY, SimilarProteinsResponse
from app.services import (
    analytics,
    annotations,
    complexes,
    compounds,
    functional,
    confidence,
    ingest,
    registry,
    similarity,
)
from app.services.external import SourceNotFoundError, SourceUnavailableError
from app.storage import local as storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proteins", tags=["proteins"])

_STATIC = Path(__file__).parent.parent / "static"

# Parsed summaries live in `services/registry` so the import router (P5) can
# register into the same store this router reads from.


@router.get("/demo/file")
def get_demo_file() -> FileResponse:
    pdb = _STATIC / "1CRN.pdb"
    if not pdb.exists():
        raise HTTPException(status_code=404, detail="Demo file not found")
    return FileResponse(str(pdb), media_type="chemical/x-pdb", filename="1CRN.pdb")


@router.post("/upload", response_model=ProteinSummary)
async def upload_protein(file: UploadFile = File(...)) -> ProteinSummary:
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in storage.ALLOWED_UPLOAD_EXTS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file extension. Allowed: pdb, cif, mmcif",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > storage.MAX_STRUCTURE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) // 1024} KB). Max 50 MB.",
        )

    try:
        uid, stored_path = storage.store_upload(content, ext)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("Failed to write uploaded file to storage")
        raise HTTPException(
            status_code=500,
            detail="Failed to store uploaded file.",
        ) from exc

    try:
        summary = await ingest.parse_and_register(stored_path, uid, source="uploaded")
    except ingest.StructureParseFailed as exc:
        # Don't leak internal path from exc — use a generic message.
        raise HTTPException(
            status_code=400,
            detail="Failed to parse structure file. Check the file is a valid PDB or mmCIF.",
        ) from exc
    except ingest.NucleicAcidOnlyError as exc:
        # The exception text is built from chain labels only, never a path.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ingest.EmptyStructureError as exc:
        # Parser returned empty structure (likely non-PDB content).
        raise HTTPException(
            status_code=400,
            detail="Could not parse any protein chains from the file. Check the file is a valid PDB or mmCIF structure.",
        ) from exc

    return summary


@router.get("/{uid}", response_model=ProteinSummary)
def get_protein(uid: str) -> ProteinSummary:
    # Validate format before cache lookup to avoid reflecting attacker input in 404 detail.
    try:
        storage.validate_uid(uid)
    except ValueError:
        raise HTTPException(status_code=404, detail="Protein not found")
    summary = registry.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail="Protein not found")
    return summary


@router.get("/{uid}/file")
def get_protein_file(uid: str) -> FileResponse:
    try:
        path = storage.get_file(uid)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc

    ext = path.suffix.lower().lstrip(".")
    media_type = "chemical/x-pdb" if ext == "pdb" else "chemical/x-mmcif"
    return FileResponse(str(path), media_type=media_type, filename=path.name)


def parse_structure_for_analytics(file_path: Path) -> Structure:
    """Parse a PDB or mmCIF file into a BioPython Structure for analytics use.

    Public because `api/compare.py` (P7) needs the same structure and the same
    analytics for two proteins at once; a second parse path would be a second
    place for the format detection to drift.
    """
    ext = file_path.suffix.lower().lstrip(".")
    if ext in ("cif", "mmcif"):
        bio_parser = MMCIFParser(QUIET=True)
    else:
        bio_parser = PDBParser(QUIET=True)
    return bio_parser.get_structure(file_path.stem, str(file_path))


def compute_analytics(
    uid: str, summary: ProteinSummary, file_path: Path
) -> AnalyticsResponse:
    """Orchestrate analytics service calls + assemble the response payload."""
    structure = parse_structure_for_analytics(file_path)

    # Aggregate composition / property distribution over all chains' sequences.
    full_seq = "".join(c.sequence for c in summary.chains)

    comp_entries = [CompositionEntry(**e) for e in analytics.composition(full_seq)]
    ss_result = analytics.secondary_structure(structure, path=file_path)
    ss = SecondaryStructurePercentages(
        helix=ss_result.helix,
        sheet=ss_result.sheet,
        coil=ss_result.coil,
        available=ss_result.available,
    )
    prop = PropertyDistribution(**analytics.property_distribution(full_seq))

    # Hydrophobicity is computed on the LONGEST chain (the "primary" chain).
    primary = (
        max(summary.chains, key=lambda c: c.residue_count) if summary.chains else None
    )
    if primary is not None:
        hp_values = analytics.hydrophobicity_profile(primary.sequence, window=9)
        hp = HydrophobicityProfile(chain_id=primary.label, window=9, values=hp_values)
    else:
        hp = HydrophobicityProfile(chain_id="", window=9, values=[])

    chain_lengths = [
        ChainLength(chain_id=c.label, length=c.residue_count) for c in summary.chains
    ]

    return AnalyticsResponse(
        id=uid,
        molecular_weight=summary.molecular_weight,
        residue_count=summary.residue_count,
        atom_count=summary.atom_count,
        chain_count=len(summary.chains),
        composition=comp_entries,
        secondary_structure=ss,
        hydrophobicity=hp,
        property_distribution=prop,
        chain_lengths=chain_lengths,
    )


@router.get("/{uid}/annotations", response_model=ProteinAnnotations)
async def get_protein_annotations(uid: str) -> ProteinAnnotations:
    """Biological annotation for a stored protein, from UniProtKB (P6).

    A protein with no resolvable UniProt accession — the normal case for a
    plain upload — is not an error. It returns 200 with every section empty
    and `accession_resolved: false`, so the panel can say *why* it is empty
    instead of showing a failure the user cannot act on.

    502 is reserved for the one case where we know the accession and UniProt
    itself could not be reached: there, retrying is worth offering.
    """
    # Imported inside the handler: `api.search` owns the client singletons, and
    # importing it at module scope would make the two routers import-cyclic.
    from app.api.search import get_rcsb_client, get_uniprot_client

    try:
        storage.validate_uid(uid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Protein not found") from exc
    summary = registry.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail="Protein not found")

    uniprot = get_uniprot_client()
    accession, note = await annotations.resolve_accession(
        summary, uniprot=uniprot, rcsb=get_rcsb_client()
    )
    if accession is None:
        logger.info("No UniProt accession for %s: %s", uid, note)
        return annotations.empty_annotations(uid, note)

    try:
        entry = await uniprot.fetch_annotations(accession)
    except SourceNotFoundError as exc:
        logger.info("UniProt has no entry for %s (protein %s): %s", accession, uid, exc)
        return annotations.empty_annotations(
            uid, f"UniProt has no entry for accession {accession}.", accession=accession
        )
    except SourceUnavailableError as exc:
        logger.warning("UniProt annotations unavailable for %s: %s", accession, exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach UniProt for this protein's annotations. Try again.",
        ) from exc

    return annotations.build_annotations(uid, entry, accession=accession, note=note)


@router.get("/{uid}/complexes", response_model=ProteinComplexes)
async def get_protein_complexes(uid: str) -> ProteinComplexes:
    """Macromolecular complexes this protein participates in, from the EBI
    Complex Portal (P9).

    The accession is resolved exactly the way P6's annotations route resolves
    it — same helper, so the two tabs can never disagree about which UniProt
    entry a structure maps to.

    Like annotations, "no complexes" is a success, not an error: most proteins
    are in none, and a plain upload has no accession to look one up with. 502
    is reserved for the case where we know the accession and Complex Portal
    itself could not be reached, because there retrying is worth offering.
    """
    from app.api.search import get_rcsb_client, get_uniprot_client

    try:
        storage.validate_uid(uid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Protein not found") from exc
    summary = registry.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail="Protein not found")

    accession, note = await annotations.resolve_accession(
        summary, uniprot=get_uniprot_client(), rcsb=get_rcsb_client()
    )
    if accession is None:
        logger.info("No UniProt accession for %s: %s", uid, note)
        return complexes.empty_complexes(uid, note)

    client = complexes.get_complex_portal_client()
    try:
        body = await client.search_by_accession(accession)
    except SourceNotFoundError as exc:
        logger.info("Complex Portal has no index for %s (protein %s): %s", accession, uid, exc)
        return complexes.empty_complexes(
            uid,
            f"The Complex Portal has no record for accession {accession}.",
            accession=accession,
            query=complexes.base_accession(accession),
        )
    except SourceUnavailableError as exc:
        logger.warning("Complex Portal unavailable for %s: %s", accession, exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach the EBI Complex Portal for this protein. Try again.",
        ) from exc

    return complexes.build_complexes(uid, body, accession=accession, note=note)


@router.get("/{uid}/functional-regions", response_model=FunctionalRegions)
async def get_functional_regions(uid: str) -> FunctionalRegions:
    """Functional regions and binding pockets for a stored protein (A5).

    Two halves with different failure modes, and they are kept independent on
    purpose:

    * The **curated** half needs UniProt. The accession is resolved with the
      same helper P6 and P9 use, so the tabs can never disagree about which
      entry a structure maps to.
    * The **observed** half — bound ligands, their contact residues, surface
      accessibility, hydropathy and charge — is measured from the coordinate
      file in front of us and needs nothing external.

    So unlike `/annotations` and `/complexes`, an upstream outage here is NOT a
    502. Throwing away a correct structural analysis because a third party is
    down would be the wrong trade; the response comes back with the curated
    lists empty and a note in `notes` saying UniProt could not be reached. See
    the tracker's decisions log, 2026-08-24.
    """
    from app.api.search import get_rcsb_client, get_uniprot_client

    try:
        storage.validate_uid(uid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Protein not found") from exc
    summary = registry.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail="Protein not found")
    try:
        file_path = storage.get_file(uid)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc

    uniprot = get_uniprot_client()
    accession, note = await annotations.resolve_accession(
        summary, uniprot=uniprot, rcsb=get_rcsb_client()
    )

    entry: dict | None = None
    curation_note = ""
    if accession is None:
        logger.info("No UniProt accession for %s: %s", uid, note)
        curation_note = (
            "No UniProt entry could be resolved for this structure, so no curated "
            "site is shown. Everything below is measured from the file itself."
        )
    else:
        try:
            entry = await uniprot.fetch_functional(accession)
        except SourceNotFoundError as exc:
            logger.info("UniProt has no entry for %s (protein %s): %s", accession, uid, exc)
            curation_note = f"UniProt has no entry for accession {accession}."
        except SourceUnavailableError as exc:
            logger.warning("UniProt functional fetch unavailable for %s: %s", accession, exc)
            curation_note = (
                "UniProt could not be reached, so curated active and binding sites are "
                "missing from this response. The observed data below is unaffected."
            )

    return await run_in_threadpool(
        _compute_functional_regions,
        uid,
        summary,
        file_path,
        accession,
        note,
        entry,
        curation_note,
    )


def _compute_functional_regions(
    uid: str,
    summary: ProteinSummary,
    file_path: Path,
    accession: str | None,
    note: str,
    entry: dict | None,
    curation_note: str,
) -> FunctionalRegions:
    """The blocking half of `/functional-regions`, for the threadpool.

    Parsing, a global alignment per chain, a neighbour search and a
    Shrake-Rupley pass are all CPU-bound; running them on the event loop would
    stall every other request for the duration.
    """
    structure = parse_structure_for_analytics(file_path)
    return functional.build_functional_regions(
        uid,
        summary,
        structure,
        accession=accession,
        resolution_note=note,
        entry=entry,
        curation_note=curation_note,
    )


@router.get("/{uid}/compounds", response_model=CompoundsResponse)
async def get_compounds(uid: str) -> CompoundsResponse:
    """Every non-protein component of a stored structure, with its contacts.

    DNA/RNA chains, ions, glycans, cofactors, free amino acids, modified
    residues, crystallisation additives and other ligands. Measured from the
    coordinate file alone, so it needs nothing external and cannot 502.
    """
    try:
        storage.validate_uid(uid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Protein not found") from exc
    summary = registry.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail="Protein not found")
    try:
        file_path = storage.get_file(uid)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc

    return await run_in_threadpool(_compute_compounds, uid, summary, file_path)


def _compute_compounds(uid: str, summary: ProteinSummary, file_path: Path) -> CompoundsResponse:
    """The blocking half of `/compounds`: one parse and a neighbour search."""
    structure = parse_structure_for_analytics(file_path)
    return compounds.build_compounds(
        uid, summary, structure, compounds.read_component_info(file_path)
    )


@router.get("/{uid}/similar", response_model=SimilarProteinsResponse)
async def get_similar_proteins(uid: str) -> SimilarProteinsResponse:
    """Precomputed homologs for a stored protein, from UniRef (P8).

    The instant half of the Similarity tab: UniRef is a clustering UniProt has
    already computed, so this answers in one or two round trips where a BLAST
    search takes minutes. Same posture as `/annotations` — an unresolvable
    accession is a 200 with an explanation, not an error.
    """
    from app.api.search import get_rcsb_client, get_uniprot_client

    try:
        storage.validate_uid(uid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Protein not found") from exc
    summary = registry.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail="Protein not found")

    uniprot = get_uniprot_client()
    accession, note = await annotations.resolve_accession(
        summary, uniprot=uniprot, rcsb=get_rcsb_client()
    )
    if accession is None:
        logger.info("No UniProt accession for %s: %s", uid, note)
        return similarity.empty_similar(uid, note)

    try:
        cluster = await uniprot.find_uniref_cluster(
            accession, identity=DEFAULT_UNIREF_IDENTITY
        )
        if cluster is None:
            return similarity.empty_similar(
                uid,
                f"{accession} is not in a UniRef{int(DEFAULT_UNIREF_IDENTITY * 100)} "
                "cluster, so there are no precomputed homologs.",
                accession=accession,
            )
        cluster_id = cluster.get("id")
        if not isinstance(cluster_id, str) or not cluster_id:
            logger.warning("UniRef cluster for %s carries no id", accession)
            return similarity.empty_similar(
                uid, "UniRef returned a cluster with no identifier.", accession=accession
            )
        members = await uniprot.fetch_uniref_members(cluster_id)
    except SourceNotFoundError as exc:
        logger.info("UniRef has nothing for %s: %s", accession, exc)
        return similarity.empty_similar(
            uid, f"UniRef has no cluster for accession {accession}.", accession=accession
        )
    except SourceUnavailableError as exc:
        logger.warning("UniRef unavailable for %s: %s", accession, exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach UniProt for this protein's homologs. Try again.",
        ) from exc

    return similarity.build_similar_proteins(
        uid, cluster, members, accession=accession, note=note
    )


#: Sources whose stored file is an AlphaFold model, so `source_id` is the
#: UniProt accession the PAE document can be looked up by. A plain upload has
#: pLDDT in the file but nothing to query AlphaFold DB with — see the import
#: router for why "uniprot" belongs here.
_ALPHAFOLD_SOURCES = ("alphafold", "uniprot")


@router.get("/{uid}/confidence", response_model=ConfidenceResponse)
async def get_protein_confidence(uid: str) -> ConfidenceResponse:
    """AlphaFold confidence analysis for a stored protein (spec A1).

    Three things this route will not do:

    * **It will not invent confidence for an experimental structure.** X-ray and
      cryo-EM entries put a temperature factor in the column AlphaFold uses for
      pLDDT, and scoring that would produce a full, entirely fictional band
      table. `has_plddt` gates the whole analysis and the response says so in
      prose.
    * **It will not fail because AlphaFold DB is down.** pLDDT comes from the
      file already on disk; PAE is a supplement. An upstream failure degrades
      the `pae` block to `available: false` with a reason and leaves the rest
      intact. This endpoint has no 502.
    * **It will not return a zeroed matrix.** Absent PAE is an absent matrix
      plus a sentence, never an all-zero grid that renders as a perfect
      prediction.
    """
    from app.api.search import get_alphafold_client

    try:
        storage.validate_uid(uid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Protein not found") from exc
    summary = registry.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail="Protein not found")

    if not summary.has_plddt:
        return confidence.not_applicable(
            uid,
            "This is an experimental structure, so it carries no pLDDT confidence "
            "scores and no predicted aligned error. Both are properties of a "
            "predicted model. Its B-factor column holds crystallographic "
            "temperature factors, which measure something different.",
        )

    try:
        file_path = storage.get_file(uid)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc

    structure = await run_in_threadpool(parse_structure_for_analytics, file_path)
    chains = confidence.extract_plddt(structure)

    accession: str | None = None
    if summary.source in _ALPHAFOLD_SOURCES and summary.source_id:
        accession = summary.source_id

    if accession is None:
        pae = confidence.unavailable_pae(
            "Predicted aligned error is published per AlphaFold DB entry, and this "
            "structure has no AlphaFold accession — it was uploaded directly, or it "
            "came from a source other than AlphaFold DB. Import the same model from "
            "AlphaFold or UniProt to see its PAE."
        )
        note = (
            "pLDDT was read from this file's B-factor column. Predicted aligned "
            "error is only available for structures imported from AlphaFold DB."
        )
    else:
        pae = await confidence.pae_matrix_for(accession, get_alphafold_client())
        note = ""

    return confidence.build_confidence(
        uid, summary, chains, pae, accession=accession, note=note
    )


@router.get("/{uid}/analytics", response_model=AnalyticsResponse)
async def get_protein_analytics(uid: str) -> AnalyticsResponse:
    try:
        storage.validate_uid(uid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Protein not found") from exc
    summary = registry.get(uid)
    if not summary:
        raise HTTPException(status_code=404, detail="Protein not found")
    try:
        file_path = storage.get_file(uid)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    return await run_in_threadpool(compute_analytics, uid, summary, file_path)
