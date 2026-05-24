"use client";

import { useEffect } from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { useStore } from "@/lib/store";
import { CompositionBarChart } from "@/components/charts/composition-bar-chart";
import { SecondaryStructureDonut } from "@/components/charts/secondary-structure-donut";
import { HydrophobicityLineChart } from "@/components/charts/hydrophobicity-line-chart";
import { ChainLengthBarChart } from "@/components/charts/chain-length-bar-chart";

interface MetricProps {
  label: string;
  value: string | number;
  unit?: string;
}

function Metric({ label, value, unit }: MetricProps) {
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-zinc-800 px-3 py-3">
      <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
        {title}
      </h3>
      {children}
    </div>
  );
}

export function AnalyticsPanel({ proteinId }: { proteinId: string }) {
  const analytics = useStore((s) => s.analytics);
  const loading = useStore((s) => s.analyticsLoading);
  const error = useStore((s) => s.analyticsError);
  const loadAnalytics = useStore((s) => s.loadAnalytics);
  const summary = useStore((s) => s.current);

  useEffect(() => {
    if (!proteinId) return;
    void loadAnalytics(proteinId);
  }, [proteinId, loadAnalytics]);

  if (loading && !analytics) {
    return (
      <div className="flex h-full items-center justify-center text-zinc-500">
        <Loader2 className="size-5 animate-spin" aria-hidden />
        <span className="ml-2 text-xs">Computing analytics&hellip;</span>
      </div>
    );
  }

  if (error && !analytics) {
    return (
      <div
        role="alert"
        className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center"
      >
        <AlertCircle className="size-6 text-red-400" aria-hidden />
        <p className="text-xs text-red-400">Analytics failed: {error.message}</p>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="flex h-full items-center justify-center px-4 text-center">
        <p className="text-xs text-zinc-500">Load a protein to see analytics.</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-2 p-3">
        <Metric label="MW" value={analytics.molecular_weight.toFixed(0)} unit="Da" />
        <Metric label="Residues" value={analytics.residue_count.toLocaleString()} />
        <Metric label="Atoms" value={analytics.atom_count.toLocaleString()} />
        <Metric label="Chains" value={analytics.chain_count} />
      </div>

      <Section title="Amino-acid composition">
        <CompositionBarChart data={analytics.composition} />
      </Section>

      <Section title="Secondary structure">
        <SecondaryStructureDonut data={analytics.secondary_structure} />
      </Section>

      <Section
        title={`Hydrophobicity — chain ${analytics.hydrophobicity.chain_id} (Kyte-Doolittle, window ${analytics.hydrophobicity.window})`}
      >
        <HydrophobicityLineChart data={analytics.hydrophobicity} />
      </Section>

      <Section title="Chain lengths">
        <ChainLengthBarChart data={analytics.chain_lengths} />
      </Section>

      {summary?.warnings && summary.warnings.length > 0 && (
        <Section title="Parser warnings">
          <ul className="space-y-1 text-[11px] text-amber-400">
            {summary.warnings.map((w, i) => (
              <li key={i}>&bull; {w}</li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}
