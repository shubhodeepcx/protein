"use client";

import { useStore } from "@/lib/store";

function Metric({
  label,
  value,
  unit,
}: {
  label: string;
  value: string | number;
  unit?: string;
}) {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/30 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-0.5 flex items-baseline gap-1">
        <span className="text-lg font-semibold text-zinc-100">{value}</span>
        {unit && <span className="text-xs text-zinc-500">{unit}</span>}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="shrink-0 text-[10px] uppercase tracking-wide text-zinc-500">
        {label}
      </span>
      <span className="truncate text-right text-xs text-zinc-200">{value}</span>
    </div>
  );
}

/** Overview tab: protein metadata plus the headline structure metrics. */
export function OverviewPanel() {
  const summary = useStore((s) => s.current);

  if (!summary) {
    return (
      <div className="flex h-full items-center justify-center px-4 text-center">
        <p className="text-xs text-zinc-500">Load a protein to see its details.</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="px-3 py-3">
        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
          Structure
        </h3>
        <div className="rounded-md border border-zinc-800 bg-zinc-900/30 px-3 py-2">
          <Field label="Name" value={summary.name?.trim() || "Unnamed"} />
          <Field label="Organism" value={summary.organism?.trim() || "Unknown"} />
          <Field
            label="Source"
            value={
              summary.source_id
                ? `${summary.source} · ${summary.source_id}`
                : summary.source
            }
          />
          <Field label="Format" value={summary.file_format.toUpperCase()} />
          {/* What the B-factor column actually holds. This is the same flag
              that gates the pLDDT coloring option and flips its scale, so
              showing it here explains why that option is or isn't offered. */}
          <Field
            label="B-factors"
            value={
              summary.has_plddt
                ? "pLDDT confidence (0–100)"
                : "Temperature factors"
            }
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 px-3 pb-3">
        <Metric label="Chains" value={summary.chains.length} />
        <Metric label="Residues" value={summary.residue_count.toLocaleString()} />
        <Metric label="Atoms" value={summary.atom_count.toLocaleString()} />
        <Metric
          label="MW"
          value={summary.molecular_weight.toFixed(0)}
          unit="Da"
        />
      </div>

      {summary.warnings.length > 0 && (
        <div className="border-t border-zinc-800 px-3 py-3">
          <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
            Parser warnings
          </h3>
          <ul className="space-y-1 text-[11px] text-amber-400">
            {summary.warnings.map((w, i) => (
              <li key={i}>&bull; {w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
