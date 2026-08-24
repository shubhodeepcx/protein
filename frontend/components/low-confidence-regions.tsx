"use client";

import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ConfidenceResponse } from "@/lib/types";

/**
 * Contiguous low-confidence stretches, as readable warnings (spec A1).
 *
 * The requirement is explicitly *warnings*, not a colour to decode: each row
 * states the chain, the residue range and the pLDDT in words. The backend
 * builds the sentence (`region.label`) so the wording cannot drift between the
 * API and the UI.
 *
 * Residue ranges are 1-based ordinals **within the chain** — the same
 * numbering the sequence panel uses.
 *
 * Sub-50 runs are marked separately from 50-70 ones because they are a
 * different claim: AlphaFold's own guidance is that below 50 often means
 * intrinsic disorder rather than a merely uncertain fold.
 */
export function LowConfidenceRegions({
  confidence,
}: {
  confidence: ConfidenceResponse;
}) {
  const { low_confidence_regions: regions, low_confidence_threshold: threshold } =
    confidence;

  if (regions.length === 0) {
    return (
      <p
        data-testid="no-low-confidence"
        role="status"
        className="flex items-start gap-1.5 px-1 text-[11px] leading-relaxed text-emerald-400"
      >
        <CheckCircle2 className="mt-0.5 size-3 shrink-0" aria-hidden />
        <span>
          No residue in this model scores below pLDDT {threshold}. Every region is
          confident or better.
        </span>
      </p>
    );
  }

  const disordered = regions.filter((r) => r.likely_disordered).length;

  return (
    <div className="flex flex-col gap-1.5">
      <p
        data-testid="low-confidence-summary"
        role="status"
        className="flex items-start gap-1.5 px-1 text-[11px] leading-relaxed text-amber-400"
      >
        <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
        <span>
          {confidence.low_confidence_residue_count} of {confidence.residue_count}{" "}
          residues ({(confidence.low_confidence_fraction * 100).toFixed(0)}%)
          score below pLDDT {threshold}, across {regions.length}{" "}
          {regions.length === 1 ? "region" : "regions"}
          {disordered > 0 && (
            <>
              {" "}
              — {disordered} of them {disordered === 1 ? "dips" : "dip"} below 50
              and {disordered === 1 ? "is" : "are"} likely disordered rather than
              merely uncertain
            </>
          )}
          .
        </span>
      </p>

      <ul data-testid="low-confidence-list" className="space-y-1 px-1">
        {regions.map((region) => (
          <li
            key={`${region.chain_id}:${region.start}-${region.end}`}
            className={`flex items-start gap-1.5 rounded border px-2 py-1 text-[11px] leading-relaxed ${
              region.likely_disordered
                ? "border-orange-900/60 bg-orange-950/20 text-orange-300"
                : "border-amber-900/50 bg-amber-950/15 text-amber-300"
            }`}
          >
            <span
              className="mt-[3px] shrink-0 rounded-[2px] px-1 text-[9px] font-semibold uppercase tracking-wide text-zinc-950"
              style={{
                background: region.likely_disordered ? "#ff7d45" : "#ffdb13",
              }}
            >
              {region.likely_disordered ? "very low" : "low"}
            </span>
            <span>{region.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
