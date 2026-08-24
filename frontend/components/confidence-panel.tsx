"use client";

import { useEffect } from "react";
import { AlertCircle, Info, Loader2 } from "lucide-react";
import { useStore } from "@/lib/store";
import { PlddtBandChart } from "@/components/charts/plddt-band-chart";
import { PaeHeatmap } from "@/components/charts/pae-heatmap";
import { LowConfidenceRegions } from "@/components/low-confidence-regions";

function SubSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <h4 className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
        {title}
      </h4>
      {children}
    </div>
  );
}

/**
 * AlphaFold confidence analysis (spec A1), folded into the Analytics tab.
 *
 * Deliberately **not** a new rail tab: `app/__tests__/landing-rail-preview.test.tsx`
 * asserts the landing page advertises exactly the tabs the rail renders, and
 * confidence is analytics about the model, so Analytics is where it belongs.
 *
 * An experimental structure is not an error and not an empty chart — it gets
 * the backend's prose note explaining that pLDDT and PAE are properties of a
 * predicted model. That is the same posture P10 gave the secondary-structure
 * donut and P7 gave the comparison warning.
 */
export function ConfidencePanel({ proteinId }: { proteinId: string }) {
  const confidence = useStore((s) => s.confidence);
  const loading = useStore((s) => s.confidenceLoading);
  const error = useStore((s) => s.confidenceError);
  const loadConfidence = useStore((s) => s.loadConfidence);

  useEffect(() => {
    if (!proteinId) return;
    void loadConfidence(proteinId);
  }, [proteinId, loadConfidence]);

  if (loading && !confidence) {
    return (
      <p className="flex items-center gap-2 px-1 text-xs text-zinc-500">
        <Loader2 className="size-3.5 animate-spin" aria-hidden />
        Reading model confidence&hellip;
      </p>
    );
  }

  if (error && !confidence) {
    return (
      <p role="alert" className="px-1 text-[11px] text-red-400">
        <AlertCircle className="mr-1 inline size-3" aria-hidden />
        Confidence analysis failed: {error.message}
      </p>
    );
  }

  if (!confidence) return null;

  if (!confidence.has_plddt) {
    return (
      <p
        data-testid="confidence-not-applicable"
        role="status"
        className="flex items-start gap-1.5 px-1 text-[11px] leading-relaxed text-zinc-400"
      >
        <Info className="mt-0.5 size-3 shrink-0 text-sky-400" aria-hidden />
        <span>{confidence.note}</span>
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-1 text-[11px] text-zinc-400">
        <span>
          Mean pLDDT{" "}
          <span
            data-testid="mean-plddt"
            className="tabular-nums text-base font-semibold text-zinc-100"
          >
            {confidence.mean_plddt?.toFixed(1) ?? "—"}
          </span>
          <span className="text-zinc-500"> / 100</span>
        </span>
        <span className="text-zinc-500">
          {confidence.residue_count} residues scored
        </span>
        {confidence.accession && (
          <span className="text-zinc-500">AlphaFold {confidence.accession}</span>
        )}
      </div>

      {confidence.note && (
        <p className="px-1 text-[11px] leading-relaxed text-zinc-500">
          {confidence.note}
        </p>
      )}

      {confidence.warnings.map((warning) => (
        <p key={warning} role="alert" className="px-1 text-[11px] text-amber-400">
          {warning}
        </p>
      ))}

      <SubSection title="Confidence bands">
        <PlddtBandChart bands={confidence.bands} />
      </SubSection>

      <SubSection title="Low-confidence regions">
        <LowConfidenceRegions confidence={confidence} />
      </SubSection>

      <SubSection title="Predicted aligned error">
        <PaeHeatmap pae={confidence.pae} />
      </SubSection>
    </div>
  );
}
