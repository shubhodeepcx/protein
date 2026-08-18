import type { SearchSource } from "@/lib/types";

const SOURCE_LABEL: Record<SearchSource, string> = {
  rcsb: "RCSB PDB",
  alphafold: "AlphaFold",
  uniprot: "UniProt",
};

// One accent per database so a mixed result list stays scannable.
const SOURCE_CLASS: Record<SearchSource, string> = {
  rcsb: "border-sky-800/70 bg-sky-950/50 text-sky-300",
  alphafold: "border-violet-800/70 bg-violet-950/50 text-violet-300",
  uniprot: "border-emerald-800/70 bg-emerald-950/50 text-emerald-300",
};

export function sourceLabel(source: SearchSource): string {
  return SOURCE_LABEL[source];
}

export function SourceBadge({ source }: { source: SearchSource }) {
  return (
    <span
      data-testid={`source-badge-${source}`}
      className={`inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${SOURCE_CLASS[source]}`}
    >
      {SOURCE_LABEL[source]}
    </span>
  );
}
