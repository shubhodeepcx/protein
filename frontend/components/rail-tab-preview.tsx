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
    source: "UniProtKB",
    items: [
      "Function, catalytic activity with EC and Rhea IDs",
      "Gene Ontology across all three aspects, and keywords",
      "Subcellular location and transmembrane spans",
      "Disease involvement, PTM/processing, and cross-references",
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
