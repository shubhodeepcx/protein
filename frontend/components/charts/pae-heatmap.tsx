"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { PaeMatrix } from "@/lib/types";
import {
  PAE_COLOR_RAMP,
  PAE_CONFIDENT_ANGSTROMS,
  paeColor,
  paeLegendTicks,
  rgbCss,
  summarisePae,
} from "@/lib/pae-scale";

/**
 * Predicted Aligned Error heatmap (spec A1).
 *
 * Drawn on a `<canvas>` at exactly one device pixel per cell and scaled up by
 * CSS, so a 128 x 128 matrix costs one DOM node rather than 16,384 of them.
 * The backend has already binned the matrix to that budget; `resolution_label`
 * states what it did and is rendered verbatim underneath.
 *
 * `available: false` never draws a grid. An experimental structure and an
 * upstream failure both render the reason instead — same treatment the
 * secondary-structure donut gives `available` after an all-coil placeholder
 * once shipped looking like a measurement.
 */
export function PaeHeatmap({ pae }: { pae: PaeMatrix }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [painted, setPainted] = useState<boolean | null>(null);

  const summary = useMemo(() => summarisePae(pae.values), [pae.values]);
  const ticks = useMemo(() => paeLegendTicks(pae.max_error), [pae.max_error]);
  const gradient = useMemo(
    () => PAE_COLOR_RAMP.map((stop) => rgbCss(stop)).join(", "),
    [],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !pae.available || pae.size === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      // jsdom, and any browser with canvas disabled. The numbers below still
      // carry the finding, so say the picture is missing rather than showing
      // a blank square that reads as "no error anywhere".
      setPainted(false);
      return;
    }
    const image = ctx.createImageData(pae.size, pae.size);
    for (let row = 0; row < pae.size; row += 1) {
      for (let col = 0; col < pae.size; col += 1) {
        const { r, g, b } = paeColor(pae.values[row]?.[col] ?? 0, pae.max_error);
        const offset = (row * pae.size + col) * 4;
        image.data[offset] = r;
        image.data[offset + 1] = g;
        image.data[offset + 2] = b;
        image.data[offset + 3] = 255;
      }
    }
    ctx.putImageData(image, 0, 0);
    setPainted(true);
  }, [pae]);

  if (!pae.available) {
    return (
      <p
        data-testid="pae-unavailable"
        role="status"
        className="flex items-start gap-1.5 px-1 text-[11px] leading-relaxed text-amber-400"
      >
        <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
        <span>
          {pae.unavailable_reason ||
            "No predicted aligned error is available for this structure."}
        </span>
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-center">
        <canvas
          ref={canvasRef}
          width={pae.size}
          height={pae.size}
          data-testid="pae-canvas"
          role="img"
          aria-label={`Predicted aligned error heatmap, ${pae.size} by ${pae.size} cells, ${pae.residue_count} residues. Median ${summary.median.toFixed(1)} angstroms, worst ${summary.worst.toFixed(1)} angstroms.`}
          className="h-auto w-full max-w-[260px] rounded border border-zinc-800 [image-rendering:pixelated]"
        />
      </div>

      {/* Legend. Real Angstrom numbers, and both ends named in words, so the
          direction of the scale is never left to be inferred from the hues. */}
      <div className="px-1">
        <div
          className="h-2 w-full rounded-sm border border-zinc-800"
          style={{ background: `linear-gradient(to right, ${gradient})` }}
          aria-hidden
        />
        <div className="mt-0.5 flex justify-between text-[10px] tabular-nums text-zinc-500">
          {ticks.map((tick) => (
            <span key={tick}>{tick.toFixed(0)}</span>
          ))}
        </div>
        <div className="flex justify-between text-[10px] text-zinc-400">
          <span>0 Å — confidently placed</span>
          <span>{pae.max_error.toFixed(1)} Å — uncertain</span>
        </div>
      </div>

      <p className="px-1 text-[11px] leading-relaxed text-zinc-400">
        Expected error in one residue&apos;s position when the model is aligned on
        another. <strong className="text-zinc-300">Lower is better</strong> — the
        opposite direction from pLDDT. Median{" "}
        <span className="tabular-nums text-zinc-200">{`${summary.median.toFixed(1)} Å`}</span>
        , worst{" "}
        <span className="tabular-nums text-zinc-200">{`${summary.worst.toFixed(1)} Å`}</span>
        ;{" "}
        <span className="tabular-nums text-zinc-200">{`${(summary.confidentFraction * 100).toFixed(0)}%`}</span>{" "}
        {`of residue pairs are within ${PAE_CONFIDENT_ANGSTROMS} Å.`}
      </p>

      <p
        data-testid="pae-resolution"
        className="px-1 text-[10px] leading-relaxed text-zinc-500"
      >
        {pae.resolution_label}
      </p>

      {painted === false && (
        <p
          data-testid="pae-canvas-unpainted"
          role="status"
          className="px-1 text-[11px] text-amber-400"
        >
          The heatmap image could not be drawn in this browser. The figures above
          are computed from the same matrix and are unaffected.
        </p>
      )}
    </div>
  );
}
