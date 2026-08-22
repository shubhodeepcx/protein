"""Project a UniProtKB entry onto `ProteinAnnotations` (P6).

Two halves, deliberately separated:

* `build_annotations` is pure — a recorded UniProtKB entry in, a Pydantic model
  out, no I/O. That is what makes the field mapping testable offline.
* `resolve_accession` does the I/O: it works out which UniProt accession (if
  any) a locally stored protein corresponds to.

Resolution never raises for "no accession". A plain upload legitimately has
none, and an upstream outage while mapping degrades to the same
unresolved-but-valid answer rather than failing the request — the same
`failed_sources` posture the P5 search fan-out takes.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from app.models.annotations import (
    CatalyticActivity,
    CrossReference,
    DiseaseAssociation,
    GeneOntology,
    GoTerm,
    KeywordEntry,
    ProteinAnnotations,
    SequenceFeature,
    SubcellularLocation,
)
from app.models.protein import ProteinSummary
from app.services.external import ExternalSourceError, Metadata, as_int
from app.services.rcsb import RCSBClient
from app.services.uniprot import (
    UniProtClient,
    normalise_accession,
    recommended_protein_name,
)

logger = logging.getLogger(__name__)

# Positional features, split into the two sections that render them.
TRANSMEMBRANE_FEATURE_TYPES = ("Transmembrane", "Topological domain")
PTM_FEATURE_TYPES = ("Signal", "Chain", "Modified residue", "Disulfide bond")

# The cross-reference databases the client asked for, in display order, with
# the URL template each one resolves through.
CROSS_REFERENCE_URLS: dict[str, str] = {
    "Reactome": "https://reactome.org/content/detail/{id}",
    "BioCyc": "https://biocyc.org/getid?id={id}",
    "SIGNOR": "https://signor.uniroma2.it/relation_result.php?id={id}",
    "NDEx": "https://www.ndexbio.org/viewer/networks/{id}",
    "Proteomes": "https://www.uniprot.org/proteomes/{id}",
}

# GO terms arrive as one cross-reference list; the term text carries the aspect.
_GO_ASPECT_ATTRIBUTES = {
    "P": "biological_process",
    "C": "cellular_component",
    "F": "molecular_function",
}


# --------------------------------------------------------------- resolution


async def resolve_accession(
    summary: ProteinSummary,
    *,
    uniprot: UniProtClient,
    rcsb: RCSBClient,
) -> tuple[str | None, str]:
    """Work out the UniProt accession for a stored protein.

    Returns `(accession, note)`; `accession` is None when there is none to
    find. The note is shown to the user, so it explains the outcome either way.
    """
    source_id = (summary.source_id or "").strip()

    if summary.source in ("uniprot", "alphafold"):
        # Both import paths are keyed by accession: AlphaFold DB has no
        # identifiers of its own, it is indexed strictly by UniProt accession.
        if not source_id:
            return None, f"This {summary.source} entry carries no accession."
        try:
            return (
                normalise_accession(source_id),
                f"Resolved directly from the {summary.source} accession.",
            )
        except ExternalSourceError:
            return None, f"{source_id!r} is not a valid UniProt accession."

    if summary.source == "rcsb":
        if not source_id:
            return None, "This RCSB entry carries no PDB identifier."
        try:
            metadata = await rcsb.fetch_metadata(source_id)
        except ExternalSourceError as exc:
            logger.warning("RCSB lookup for %s failed while resolving: %s", source_id, exc)
        else:
            accession = metadata.get("uniprot_accession")
            if isinstance(accession, str) and accession:
                return (
                    accession,
                    f"Mapped from PDB {source_id.upper()} via its polymer entity.",
                )

        # No cross-reference on the entity (or RCSB was unreachable): ask
        # UniProt which entry cross-references this PDB id.
        try:
            found = await uniprot.find_accession_for_pdb(source_id.upper())
        except ExternalSourceError as exc:
            logger.warning("UniProt PDB mapping for %s failed: %s", source_id, exc)
            return None, "Could not reach UniProt to map this PDB entry. Try again."
        if found:
            return found, f"Mapped from PDB {source_id.upper()} via UniProt's index."
        return None, f"No UniProt entry cross-references PDB {source_id.upper()}."

    return None, "Uploaded structures carry no database identifier to map from."


# --------------------------------------------------------------- projection


def build_annotations(
    uid: str,
    entry: Metadata,
    *,
    accession: str,
    note: str,
) -> ProteinAnnotations:
    """Flatten a UniProtKB entry into the annotation payload. Pure."""
    organism = entry.get("organism") or {}
    comments = _as_list(entry.get("comments"))
    features = _as_list(entry.get("features"))
    cross_refs = _as_list(entry.get("uniProtKBCrossReferences"))

    return ProteinAnnotations(
        id=uid,
        accession=accession,
        accession_resolved=True,
        resolution_note=note,
        entry_name=_text(entry.get("uniProtkbId")),
        protein_name=recommended_protein_name(entry),
        gene_names=_gene_names(entry),
        organism=_text(organism.get("scientificName")),
        taxon_id=as_int(organism.get("taxonId")),
        lineage=[t for t in (_text(v) for v in _as_list(organism.get("lineage"))) if t],
        function=_comment_texts(comments, "FUNCTION"),
        catalytic_activity=_catalytic_activity(comments),
        gene_ontology=_gene_ontology(cross_refs),
        keywords=_keywords(entry),
        subcellular_locations=_subcellular_locations(comments),
        subcellular_location_notes=_subcellular_location_notes(comments),
        transmembrane=_features(features, TRANSMEMBRANE_FEATURE_TYPES),
        diseases=_diseases(comments),
        ptm=_comment_texts(comments, "PTM"),
        ptm_features=_features(features, PTM_FEATURE_TYPES),
        cross_references=_cross_references(cross_refs),
    )


def empty_annotations(uid: str, note: str, accession: str | None = None) -> ProteinAnnotations:
    """A valid, entirely empty payload — every section hides itself."""
    return ProteinAnnotations(
        id=uid, accession=accession, accession_resolved=False, resolution_note=note
    )


# ------------------------------------------------------------------ helpers


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object) -> str | None:
    """A non-empty stripped string, or None. Untrusted JSON in, str|None out."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _gene_names(entry: Metadata) -> list[str]:
    """Primary gene name first, then synonyms / ORF / ordered-locus names."""
    names: list[str] = []
    for gene in _as_list(entry.get("genes")):
        if not isinstance(gene, dict):
            continue
        candidates: list[object] = [(gene.get("geneName") or {}).get("value")]
        for key in ("synonyms", "orfNames", "orderedLocusNames"):
            for alias in _as_list(gene.get(key)):
                if isinstance(alias, dict):
                    candidates.append(alias.get("value"))
        for candidate in candidates:
            name = _text(candidate)
            if name and name not in names:
                names.append(name)
    return names


def _comments_of(comments: list[object], comment_type: str) -> list[dict[str, object]]:
    return [
        c
        for c in comments
        if isinstance(c, dict) and c.get("commentType") == comment_type
    ]


def _texts_of(comment: dict[str, object], key: str = "texts") -> list[str]:
    out: list[str] = []
    for text in _as_list(comment.get(key)):
        if isinstance(text, dict):
            value = _text(text.get("value"))
            if value:
                out.append(value)
    return out


def _comment_texts(comments: list[object], comment_type: str) -> list[str]:
    """Every paragraph of a free-text comment block, untruncated.

    Search cards trim the FUNCTION comment to a blurb; the panel is where the
    whole thing belongs, so nothing is shortened here.
    """
    return [
        paragraph
        for comment in _comments_of(comments, comment_type)
        for paragraph in _texts_of(comment)
    ]


def _catalytic_activity(comments: list[object]) -> list[CatalyticActivity]:
    activities: list[CatalyticActivity] = []
    for comment in _comments_of(comments, "CATALYTIC ACTIVITY"):
        reaction = comment.get("reaction")
        if not isinstance(reaction, dict):
            continue
        rhea_ids: list[str] = []
        chebi_ids: list[str] = []
        for ref in _as_list(reaction.get("reactionCrossReferences")):
            if not isinstance(ref, dict):
                continue
            ref_id = _text(ref.get("id"))
            if not ref_id:
                continue
            if ref.get("database") == "Rhea":
                rhea_ids.append(ref_id)
            elif ref.get("database") == "ChEBI":
                chebi_ids.append(ref_id)
        activities.append(
            CatalyticActivity(
                reaction=_text(reaction.get("name")),
                ec_number=_text(reaction.get("ecNumber")),
                rhea_ids=rhea_ids,
                chebi_ids=chebi_ids,
            )
        )
    return activities


def _gene_ontology(cross_refs: list[object]) -> GeneOntology:
    """Sort GO cross-references into the ontology's three aspects.

    UniProt encodes the aspect as a one-letter prefix on the term text
    (`C:extracellular space`) rather than as a field of its own — the `go_c` /
    `go_p` / `go_f` return fields select which of these appear, they do not
    arrive separated.
    """
    ontology = GeneOntology()
    for ref in cross_refs:
        if not isinstance(ref, dict) or ref.get("database") != "GO":
            continue
        go_id = _text(ref.get("id"))
        if not go_id:
            continue
        properties = _properties(ref)
        raw_term = properties.get("GoTerm")
        if not raw_term or len(raw_term) < 3 or raw_term[1] != ":":
            continue
        attribute = _GO_ASPECT_ATTRIBUTES.get(raw_term[0])
        if attribute is None:
            continue
        evidence = properties.get("GoEvidenceType")
        getattr(ontology, attribute).append(
            GoTerm(
                id=go_id,
                term=raw_term[2:].strip(),
                # "IDA:UniProtKB" — the code is the part before the source.
                evidence=evidence.split(":", 1)[0] if evidence else None,
            )
        )
    return ontology


def _properties(ref: dict[str, object]) -> dict[str, str]:
    """The `properties` list of a cross-reference as a plain dict.

    UniProt writes a missing value as "-", which is noise, not data.
    """
    out: dict[str, str] = {}
    for prop in _as_list(ref.get("properties")):
        if not isinstance(prop, dict):
            continue
        key = _text(prop.get("key"))
        value = _text(prop.get("value"))
        if key and value and value != "-":
            out[key] = value
    return out


def _keywords(entry: Metadata) -> list[KeywordEntry]:
    keywords: list[KeywordEntry] = []
    for keyword in _as_list(entry.get("keywords")):
        if not isinstance(keyword, dict):
            continue
        name = _text(keyword.get("name"))
        if not name:
            continue
        keywords.append(
            KeywordEntry(
                id=_text(keyword.get("id")),
                name=name,
                category=_text(keyword.get("category")),
            )
        )
    return keywords


def _subcellular_locations(comments: list[object]) -> list[SubcellularLocation]:
    locations: list[SubcellularLocation] = []
    for comment in _comments_of(comments, "SUBCELLULAR LOCATION"):
        for entry in _as_list(comment.get("subcellularLocations")):
            if not isinstance(entry, dict):
                continue
            location = _text((entry.get("location") or {}).get("value"))
            if not location:
                continue
            locations.append(
                SubcellularLocation(
                    location=location,
                    topology=_text((entry.get("topology") or {}).get("value")),
                )
            )
    return locations


def _subcellular_location_notes(comments: list[object]) -> list[str]:
    notes: list[str] = []
    for comment in _comments_of(comments, "SUBCELLULAR LOCATION"):
        note = comment.get("note")
        if isinstance(note, dict):
            notes.extend(_texts_of(note))
    return notes


def _diseases(comments: list[object]) -> list[DiseaseAssociation]:
    diseases: list[DiseaseAssociation] = []
    for comment in _comments_of(comments, "DISEASE"):
        disease = comment.get("disease")
        if not isinstance(disease, dict):
            continue
        name = _text(disease.get("diseaseId"))
        if not name:
            continue
        reference = disease.get("diseaseCrossReference")
        mim_id: str | None = None
        if isinstance(reference, dict) and reference.get("database") == "MIM":
            mim_id = _text(reference.get("id"))
        diseases.append(
            DiseaseAssociation(
                name=name,
                acronym=_text(disease.get("acronym")),
                description=_text(disease.get("description")),
                mim_id=mim_id,
            )
        )
    return diseases


def _features(features: list[object], types: tuple[str, ...]) -> list[SequenceFeature]:
    """Positional features of the given types, in sequence order."""
    selected: list[SequenceFeature] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        feature_type = _text(feature.get("type"))
        if feature_type not in types:
            continue
        location = feature.get("location") or {}
        selected.append(
            SequenceFeature(
                type=feature_type or "",
                description=_text(feature.get("description")),
                start=as_int((location.get("start") or {}).get("value")),
                end=as_int((location.get("end") or {}).get("value")),
            )
        )
    return selected


def _cross_references(cross_refs: list[object]) -> list[CrossReference]:
    """Pathway / network / proteome cross-references, as outbound links."""
    references: list[CrossReference] = []
    for ref in cross_refs:
        if not isinstance(ref, dict):
            continue
        database = _text(ref.get("database"))
        ref_id = _text(ref.get("id"))
        if database not in CROSS_REFERENCE_URLS or not ref_id:
            continue
        properties = _properties(ref)
        # UniProt names the label property differently per database; take
        # whichever one this entry carries rather than hard-coding each.
        description = next(iter(properties.values()), None)
        references.append(
            CrossReference(
                database=database or "",
                id=ref_id,
                description=description,
                # BioCyc ids embed a colon ("MetaCyc:MONOMER-…"), so the id is
                # percent-encoded rather than pasted into the template raw.
                url=CROSS_REFERENCE_URLS[database or ""].format(id=quote(ref_id, safe="")),
            )
        )
    return references
