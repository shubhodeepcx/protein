"use client";

import { useEffect } from "react";
import { AlertCircle, Info, Loader2 } from "lucide-react";
import { useStore } from "@/lib/store";
import {
  CompoundCategorySection,
  NucleicAcidSection,
} from "@/components/compounds-sections";
import type { CompoundCategory, CompoundGroup } from "@/lib/types";

/** Same order the backend ranks groups in: biological partners first. */
const CATEGORY_ORDER: readonly CompoundCategory[] = [
  "ligand",
  "cofactor",
  "ion",
  "carbohydrate",
  "free_amino_acid",
  "modified_residue",
  "additive",
];

/**
 * Compounds tab: everything in the file that is related to the protein but is
 * not the protein. DNA/RNA, ligands, cofactors, ions, glycans, free amino
 * acids, modified residues and crystallisation additives, each with the
 * protein residues it touches.
 *
 * All of it is measured from the coordinate file, so there is no upstream to
 * fail; an empty result is a fact about the structure and is said plainly.
 */
export function CompoundsPanel({ proteinId }: { proteinId: string }) {
  const compounds = useStore((s) => s.compounds);
  const loading = useStore((s) => s.compoundsLoading);
  const error = useStore((s) => s.compoundsError);
  const loadCompounds = useStore((s) => s.loadCompounds);

  useEffect(() => {
    if (!proteinId) return;
    void loadCompounds(proteinId);
  }, [proteinId, loadCompounds]);

  if (loading && !compounds) {
    return (
      <div className="flex h-full items-center justify-center text-zinc-500">
        <Loader2 className="size-5 animate-spin" aria-hidden />
        <span className="ml-2 text-xs">Reading compounds&hellip;</span>
      </div>
    );
  }

  if (error && !compounds) {
    return (
      <div
        role="alert"
        className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center"
      >
        <AlertCircle className="size-6 text-red-400" aria-hidden />
        <p className="text-xs text-red-400">Compounds failed: {error.message}</p>
      </div>
    );
  }

  if (!compounds) {
    return (
      <div className="flex h-full items-center justify-center px-4 text-center">
        <p className="text-xs text-zinc-500">Load a protein to see its compounds.</p>
      </div>
    );
  }

  const byCategory = new Map<CompoundCategory, CompoundGroup[]>();
  for (const group of compounds.groups) {
    byCategory.set(group.category, [...(byCategory.get(group.category) ?? []), group]);
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto" data-testid="compounds-panel">
      <div className="space-y-1.5 border-b border-zinc-800 px-3 py-2.5">
        {compounds.notes.map((note) => (
          <p key={note} className="flex gap-1.5 text-[10px] leading-relaxed text-zinc-400">
            <Info className="mt-px size-3 shrink-0 text-zinc-500" aria-hidden />
            <span>{note}</span>
          </p>
        ))}
        {compounds.water_count > 0 && (
          <p className="text-[10px] text-zinc-500">
            {compounds.water_count} water molecule
            {compounds.water_count === 1 ? "" : "s"} in the file (not listed).
          </p>
        )}
      </div>
      <NucleicAcidSection chains={compounds.nucleic_acids} />
      {CATEGORY_ORDER.map((category) => (
        <CompoundCategorySection
          key={category}
          category={category}
          groups={byCategory.get(category) ?? []}
        />
      ))}
    </div>
  );
}
