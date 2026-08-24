"use client";

import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { ResidueRef } from "@/lib/types";

/**
 * The residue chips shared by every functional-region section.
 *
 * Clicking one drives the *existing* `setSelection` in
 * `lib/store/selection-slice.ts` — the same call the sequence panel and the
 * chain tree make — so a click here highlights in 3D through the machinery
 * that already exists, and a 3D click lights the chip back up. There is no
 * second selection path.
 *
 * A chip is labelled with its **ordinal**, because that is the coordinate the
 * selection key is in and the number the sequence panel prints. The file's own
 * residue number goes in the tooltip, where it cannot be mistaken for one.
 */

function refTitle(ref: ResidueRef): string {
  const authored =
    ref.auth_seq_id === null
      ? "no number in the file"
      : `numbered ${ref.auth_seq_id}${ref.insertion_code ?? ""} in the file`;
  return `Select ${ref.key} — residue ${ref.ordinal} of chain ${ref.chain}, ${authored}`;
}

export function ResidueChip({ residue }: { residue: ResidueRef }) {
  const setSelection = useStore((s) => s.setSelection);
  const selected = useStore((s) => s.selected.has(residue.key));

  return (
    <button
      type="button"
      onClick={() => setSelection([residue.key])}
      title={refTitle(residue)}
      data-testid={`functional-residue-${residue.key}`}
      aria-pressed={selected}
      className={cn(
        "rounded border px-1.5 py-0.5 font-mono text-[10px] tabular-nums",
        selected
          ? "border-sky-500 bg-sky-500/20 text-sky-200"
          : "border-zinc-800 bg-zinc-900/40 text-zinc-300 hover:border-zinc-600 hover:text-zinc-100",
      )}
    >
      {residue.residue}
      {residue.chain}:{residue.ordinal}
    </button>
  );
}

/** A row of chips plus a "select all" when there is more than one. */
export function ResidueChips({
  residues,
  label,
}: {
  residues: ResidueRef[];
  label: string;
}) {
  const setSelection = useStore((s) => s.setSelection);
  if (residues.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1">
      {residues.map((residue) => (
        <ResidueChip key={residue.key} residue={residue} />
      ))}
      {residues.length > 1 && (
        <button
          type="button"
          onClick={() => setSelection(residues.map((r) => r.key))}
          title={`Select all ${residues.length} residues of ${label}`}
          className="rounded border border-dashed border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-400 hover:border-zinc-500 hover:text-zinc-100"
        >
          all {residues.length}
        </button>
      )}
    </div>
  );
}

/**
 * Why a site has no residues to show.
 *
 * This is the honest half of the feature and it is styled to be read, not
 * skipped: a curated site that this construct does not contain is a fact about
 * the structure, and the alternative to saying so is guessing a position.
 */
export function Unplaced({ note }: { note: string }) {
  return (
    <p className="rounded border border-amber-900/60 bg-amber-950/30 px-2 py-1 text-[10px] leading-relaxed text-amber-300/90">
      {note}
    </p>
  );
}

/** Evidence badge. A sequence-rule inference must not read like an observation. */
export function EvidenceBadge({ experimental }: { experimental: boolean }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded px-1 py-px text-[9px] uppercase tracking-wide",
        experimental
          ? "bg-emerald-950/60 text-emerald-300"
          : "bg-zinc-800 text-zinc-400",
      )}
      title={
        experimental
          ? "Backed by experimental evidence in UniProt (ECO:0000269 / ECO:0007744)"
          : "Inferred by UniProt from a sequence rule or similarity, not observed"
      }
    >
      {experimental ? "experimental" : "inferred"}
    </span>
  );
}
