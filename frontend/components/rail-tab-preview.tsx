import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export interface RailTab {
  value: string;
  title: string;
  /** Where the panel's data comes from. Named so the claim is checkable. */
  source: string;
  /** What the tab shows today — not what it is planned to show. */
  items: readonly string[];
}

/**
 * The landing page's preview of the viewer rail.
 *
 * This copy has drifted from reality twice already: it once promised features
 * that had shipped as though they were still to come, and it listed three tabs
 * for months after the rail grew to five. Every line below names something the
 * viewer renders right now, so the honest way to change it is to change it
 * when the rail changes.
 */
export const RAIL_TABS: readonly RailTab[] = [
  {
    value: "overview",
    title: "Overview",
    source: "Structure file",
    items: [
      "Name, organism, source database and accession",
      "File format, and whether B-factors hold pLDDT confidence",
      "Chains, residues, atoms and molecular weight",
      "Parser warnings, when the file raised any",
    ],
  },
  {
    value: "sequence",
    title: "Sequence",
    source: "Structure file",
    items: [
      "One-letter sequence per chain on a clickable grid",
      "Coloured by residue class, with a position ruler",
      "Click a residue to highlight it in 3D — and the reverse",
      "Find a residue by chain and position, e.g. A:12",
    ],
  },
  {
    value: "analytics",
    title: "Analytics",
    source: "Computed server-side",
    items: [
      "Amino-acid composition across all 20 residues",
      "Secondary-structure split — or a plain warning when the file assigns none",
      "Kyte-Doolittle hydrophobicity along the longest chain",
      "Chain lengths side by side",
    ],
  },
  {
    value: "annotations",
    title: "Annotations",
    source: "UniProtKB + this structure",
    items: [
      "Function, catalytic activity with EC and Rhea IDs",
      "Gene Ontology across all three aspects, and keywords",
      "Subcellular location, transmembrane spans, disease and PTM",
      "Curated active and ligand-binding sites, mapped onto the residues this file really contains — or refused when they cannot be",
      "Ligands bound in the file, and the residues within 4 Å of them",
      "Per-chain surface hydrophobicity and charge",
    ],
  },
  {
    value: "similarity",
    title: "Similarity",
    source: "EBI NCBI BLAST, UniRef",
    items: [
      "Precomputed UniRef homologs, returned immediately",
      "BLAST search against UniProtKB and the ENA nucleotide sets",
      "blastp, blastn, tblastn and blastx, with live progress",
      "Identity, E-value and score per hit, each openable in the viewer",
    ],
  },
  {
    value: "complexes",
    title: "Complexes",
    source: "EBI Complex Portal",
    items: [
      "Every curated complex this protein participates in",
      "Participants with their stoichiometry",
      "Links back to the Complex Portal record",
    ],
  },
];

/** One tab's preview card. Static — no protein is loaded on the landing page. */
export function RailTabPreview({ tab }: { tab: RailTab }) {
  return (
    <Card className="gap-3 border-dashed py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-sm">{tab.title}</CardTitle>
        <CardDescription className="text-[11px]">
          {tab.source} &middot; shown once a protein is loaded
        </CardDescription>
      </CardHeader>
      <CardContent className="px-4">
        <ul className="space-y-1.5 text-[11px] leading-relaxed text-muted-foreground">
          {tab.items.map((item) => (
            <li key={item} className="flex gap-2">
              <span aria-hidden className="text-primary">
                &bull;
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export interface DataSource {
  name: string;
  /** The host the backend actually talks to. Checkable against `backend/app/services/`. */
  host: string;
  body: string;
}

/**
 * The four public services this app is wired to. Each host below appears in a
 * client under `backend/app/services/`, so this list is falsifiable rather
 * than aspirational — which is the standard the landing page failed before.
 */
export const DATA_SOURCES: readonly DataSource[] = [
  {
    name: "RCSB PDB",
    host: "data.rcsb.org",
    body: "Experimental structures — search, import, and the mmCIF or PDB coordinates themselves.",
  },
  {
    name: "AlphaFold DB",
    host: "alphafold.ebi.ac.uk",
    body: "Predicted models, imported with pLDDT confidence in the B-factor column and coloured for it.",
  },
  {
    name: "UniProtKB",
    host: "rest.uniprot.org",
    body: "Function, catalytic activity, GO, keywords, location, disease and PTM for the Annotations tab.",
  },
  {
    name: "Complex Portal",
    host: "ebi.ac.uk/intact",
    body: "Curated macromolecular complexes containing the protein, with their participants and stoichiometry.",
  },
];

/** A compact card per integrated database. */
export function DataSourceCard({ source }: { source: DataSource }) {
  return (
    <div className="rounded-md border border-border/60 bg-card/40 px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold">{source.name}</span>
        <span className="truncate font-mono text-[10px] text-muted-foreground">
          {source.host}
        </span>
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
        {source.body}
      </p>
    </div>
  );
}
