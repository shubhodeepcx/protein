"use client";

import { useEffect } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { useStore } from "@/lib/store";
import {
  CuratedSiteSection,
  LigandSection,
  PrioritySection,
} from "@/components/functional-sections";
import { MappingSection, SurfaceSection } from "@/components/functional-surface";

/**
 * A5 — functional regions and binding pockets, inside the Annotations tab.
 *
 * ## Why it lives here and not in a seventh rail tab
 *
 * A5's first two bullets are four more UniProt positional feature types
 * (`ft_act_site`, `ft_binding`, `ft_site`, `ft_dna_bind`) alongside the ones
 * this tab already renders — transmembrane spans, signal peptides, chains,
 * disulfide bonds. Splitting them into their own tab would put one source's
 * features in two places. The structure-observed half — bound ligands, their
 * contacts, the surface profile — attaches to the *same residues*, and the one
 * genuinely valuable thing this feature produces is seeing that a curator and
 * this file agree on a residue. That only reads if they are side by side.
 *
 * The rail also already carries six tabs at 24rem; a seventh is the change
 * P10's decisions log declined to make for a measured reason.
 *
 * ## What it does not show
 *
 * Predicted pockets. A5 lists them and Phase 2 is where an ML scorer would go;
 * a geometric cavity search shipped under that label now would be a heuristic
 * wearing a prediction's clothes. The only pockets here are observed ones, and
 * an apo structure is told so rather than shown a guess.
 */
export function FunctionalRegionsPanel({ proteinId }: { proteinId: string }) {
  const functional = useStore((s) => s.functional);
  const loading = useStore((s) => s.functionalLoading);
  const error = useStore((s) => s.functionalError);
  const loadFunctional = useStore((s) => s.loadFunctional);

  useEffect(() => {
    if (!proteinId) return;
    void loadFunctional(proteinId);
  }, [proteinId, loadFunctional]);

  if (loading && !functional) {
    return (
      <div className="flex items-center justify-center gap-2 border-b border-zinc-800 px-3 py-4 text-zinc-500">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        <span className="text-xs">Locating functional regions&hellip;</span>
      </div>
    );
  }

  if (error && !functional) {
    return (
      <div
        role="alert"
        className="flex items-center gap-2 border-b border-zinc-800 px-3 py-3 text-xs text-red-400"
      >
        <AlertCircle className="size-4 shrink-0" aria-hidden />
        <span>Functional regions failed: {error.message}</span>
      </div>
    );
  }

  if (!functional) return null;

  return (
    <>
      <CuratedSiteSection title="Active sites" sites={functional.active_sites} />
      <CuratedSiteSection title="Ligand-binding sites" sites={functional.binding_sites} />
      <CuratedSiteSection title="DNA-binding regions" sites={functional.dna_binding} />
      <CuratedSiteSection title="Other functional sites" sites={functional.other_sites} />
      <LigandSection ligands={functional.ligands} cutoff={functional.contact_cutoff} />
      <PrioritySection residues={functional.priority_residues} />
      <SurfaceSection profiles={functional.surface} note={functional.surface_note} />
      <MappingSection mappings={functional.chain_mappings} />
      <ul
        data-testid="functional-notes"
        className="space-y-1 px-3 py-3 text-[10px] leading-relaxed text-zinc-600"
      >
        {functional.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </>
  );
}
