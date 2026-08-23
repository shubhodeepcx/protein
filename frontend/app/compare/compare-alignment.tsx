"use client";

import { useMemo } from "react";
import { AlertTriangle, Info } from "lucide-react";
import { alignmentBlocks } from "@/lib/alignment-blocks";
import { formatNumber } from "@/lib/compare-format";
import type { SequenceAlignment, Superposition } from "@/lib/types";

/** Columns per block — the width EMBOSS and BLAST print. */
const BLOCK_WIDTH = 60;

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/30 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-100">
        {value}
      </div>
      {hint && <div className="mt-0.5 text-[10px] text-zinc-600">{hint}</div>}
    </div>
  );
}

/** A note the comparison returns in place of a result — never an error. */
export function CompareNote({
  children,
  testId,
}: {
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <p
      data-testid={testId}
      role="status"
      className="flex items-start gap-1.5 rounded-md border border-zinc-800 bg-zinc-900/30 px-3 py-2 text-[11px] leading-relaxed text-zinc-400"
    >
      <Info className="mt-0.5 size-3 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}

/**
 * Superposition RMSD, or the reason there is none.
 *
 * `caveat` is rendered as prominently as the number it qualifies. An RMSD from
 * a twilight-zone alignment or from five atom pairs is a real number computed
 * from an unreliable pairing, and showing it bare would be the worst outcome —
 * confident, precise, and wrong.
 */
export function SuperpositionCard({
  superposition,
  note,
}: {
  superposition: Superposition | null;
  note: string;
}) {
  if (!superposition) {
    return <CompareNote testId="superposition-note">{note}</CompareNote>;
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat
          label="RMSD"
          value={`${superposition.rmsd.toFixed(2)} Å`}
          hint={`chain ${superposition.chain_a} vs ${superposition.chain_b}`}
        />
        <Stat
          label="Atom pairs"
          value={formatNumber(superposition.atom_pairs)}
          hint="alpha carbons fitted"
        />
        <Stat
          label="Residue pairs"
          value={formatNumber(superposition.residue_pairs)}
          hint="aligned, CA or not"
        />
      </div>
      {superposition.caveat && (
        <p
          data-testid="superposition-caveat"
          role="status"
          className="flex items-start gap-1.5 text-[11px] leading-relaxed text-amber-400"
        >
          <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
          <span>{superposition.caveat}</span>
        </p>
      )}
      <p className="text-[11px] text-zinc-600">{note}</p>
    </div>
  );
}

/** Identity / similarity / length, then the alignment itself in numbered blocks. */
export function AlignmentPanel({
  alignment,
  note,
}: {
  alignment: SequenceAlignment | null;
  note: string;
}) {
  const blocks = useMemo(
    () =>
      alignment
        ? alignmentBlocks(
            alignment.aligned_a,
            alignment.match_line,
            alignment.aligned_b,
            BLOCK_WIDTH,
          )
        : [],
    [alignment],
  );

  if (!alignment) {
    return <CompareNote testId="alignment-note">{note}</CompareNote>;
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat
          label="Identity"
          value={`${alignment.identity_percent.toFixed(1)}%`}
          hint={`${formatNumber(alignment.identities)} of ${formatNumber(alignment.alignment_length)} columns`}
        />
        <Stat
          label="Similarity"
          value={`${alignment.similarity_percent.toFixed(1)}%`}
          hint={`${formatNumber(alignment.similarities)} positive BLOSUM62`}
        />
        <Stat
          label="Alignment length"
          value={formatNumber(alignment.alignment_length)}
          hint={`${formatNumber(alignment.gap_columns)} gap columns`}
        />
        <Stat
          label="Identity, overlap"
          value={`${alignment.identity_percent_aligned.toFixed(1)}%`}
          hint={`over ${formatNumber(alignment.aligned_columns)} shared columns`}
        />
      </div>

      <p className="text-[11px] text-zinc-600">{note}</p>

      <div className="overflow-x-auto rounded-md border border-zinc-800 bg-zinc-950 p-3">
        <pre
          data-testid="alignment-blocks"
          className="font-mono text-[11px] leading-[1.35]"
        >
          {blocks.map((block) => (
            <span key={block.column} className="block whitespace-pre">
              <span className="block text-zinc-300">
                {`A ${String(block.startA ?? "").padStart(5)} ${block.rowA} ${block.endA ?? ""}`}
              </span>
              {/* Conserved and divergent columns, BLAST's notation: '|'
                  identical, '+' conservative substitution, blank neither. */}
              <span className="block text-sky-400">
                {`  ${" ".repeat(5)} ${block.match}`}
              </span>
              <span className="block text-zinc-300">
                {`B ${String(block.startB ?? "").padStart(5)} ${block.rowB} ${block.endB ?? ""}`}
              </span>
              <span className="block">&nbsp;</span>
            </span>
          ))}
        </pre>
      </div>

      <p className="text-[10px] text-zinc-600">
        <span className="text-sky-400">|</span> identical ·{" "}
        <span className="text-sky-400">+</span> conservative substitution
        (positive BLOSUM62) · blank neither
      </p>
    </div>
  );
}
