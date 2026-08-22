/**
 * Outbound links for the identifiers the annotation panel renders.
 *
 * The backend already resolves pathway/network/proteome cross-references to a
 * URL — it knows which databases it selected. These are the identifiers that
 * arrive as bare strings inside other sections (GO terms, Rhea reactions, EC
 * numbers, OMIM ids), so their templates live on this side.
 *
 * Every helper returns `null` for input it cannot form a real URL from. A dead
 * link is worse than no link: it looks like data and isn't.
 */

const GO_ID = /^GO:\d{7}$/;
const RHEA_ID = /^RHEA:\d+$/;
const CHEBI_ID = /^CHEBI:\d+$/;
const EC_NUMBER = /^\d+(\.(\d+|-)){0,3}$/;
const DIGITS = /^\d+$/;

/** QuickGO, the EBI's GO term browser. */
export function goUrl(id: string): string | null {
  return GO_ID.test(id) ? `https://www.ebi.ac.uk/QuickGO/term/${id}` : null;
}

/** Rhea, which is where `cc_catalytic_activity`'s reaction ids point. */
export function rheaUrl(id: string): string | null {
  if (!RHEA_ID.test(id)) return null;
  return `https://www.rhea-db.org/rhea/${id.slice("RHEA:".length)}`;
}

/** ChEBI, for the reaction participants Rhea references. */
export function chebiUrl(id: string): string | null {
  if (!CHEBI_ID.test(id)) return null;
  return `https://www.ebi.ac.uk/chebi/searchId.do?chebiId=${id}`;
}

/** ExPASy ENZYME. Partial EC numbers ("2.7.10.-") resolve to the class page. */
export function ecUrl(ec: string): string | null {
  return EC_NUMBER.test(ec) ? `https://enzyme.expasy.org/EC/${ec}` : null;
}

/** OMIM, for the disease cross-references UniProt carries. */
export function omimUrl(id: string): string | null {
  return DIGITS.test(id) ? `https://www.omim.org/entry/${id}` : null;
}

/** The UniProtKB entry itself — the panel's "source" link. */
export function uniprotUrl(accession: string): string | null {
  return /^[A-Z0-9]{6,10}(-\d+)?$/.test(accession)
    ? `https://www.uniprot.org/uniprotkb/${accession}`
    : null;
}

/** NCBI Taxonomy, reached from the entry's taxon id. */
export function taxonomyUrl(taxonId: number): string | null {
  return Number.isInteger(taxonId) && taxonId > 0
    ? `https://www.uniprot.org/taxonomy/${taxonId}`
    : null;
}

/** A 1-based inclusive residue range, rendered the way UniProt writes it. */
export function formatRange(start: number | null, end: number | null): string {
  if (start === null && end === null) return "";
  if (start !== null && end !== null) {
    return start === end ? `${start}` : `${start}–${end}`;
  }
  return `${start ?? end}`;
}
