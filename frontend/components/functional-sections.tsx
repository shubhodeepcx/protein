"use client";

import { AnnotationSection } from "@/components/annotation-section";
import {
  EvidenceBadge,
  ResidueChip,
  ResidueChips,
  Unplaced,
} from "@/components/functional-residues";
import { useStore } from "@/lib/store";
import type { BoundLigand, CuratedSite, PriorityResidue } from "@/lib/types";

/** Curated UniProt sites — active, ligand-binding, other, DNA-binding. */
export function CuratedSiteSection({
  title,
  sites,
}: {
  title: string;
  sites: CuratedSite[];
}) {
  if (sites.length === 0) return null;
  return (
    <AnnotationSection title={title} count={sites.length}>
      <ul className="space-y-2">
        {sites.map((site) => (
          <li key={`${site.kind}-${site.uniprot_start}-${site.uniprot_end}`}>
            <div className="flex items-baseline gap-2">
              <span className="text-xs text-zinc-200">{site.label}</span>
              <EvidenceBadge experimental={site.experimental} />
              <span className="ml-auto shrink-0 font-mono text-[10px] text-zinc-500">
                UniProt{" "}
                {site.uniprot_start === site.uniprot_end
                  ? site.uniprot_start
                  : `${site.uniprot_start}-${site.uniprot_end}`}
              </span>
            </div>
            {site.description && site.label !== `${title}: ${site.description}` && (
              <p className="mt-0.5 text-[11px] leading-relaxed text-zinc-400">
                {site.description}
              </p>
            )}
            <div className="mt-1">
              {site.located ? (
                <ResidueChips residues={site.positions} label={site.label} />
              ) : (
                <Unplaced note={site.location_note} />
              )}
            </div>
            {site.located && site.location_note && (
              <p className="mt-1 text-[10px] text-amber-300/80">{site.location_note}</p>
            )}
            {site.substitutions.map((line) => (
              <p key={line} className="mt-1 text-[10px] text-amber-300/80">
                {line}
              </p>
            ))}
          </li>
        ))}
      </ul>
    </AnnotationSection>
  );
}

/** Bound ligands and the residues they touch — observed, never predicted. */
export function LigandSection({
  ligands,
  cutoff,
}: {
  ligands: BoundLigand[];
  cutoff: number;
}) {
  if (ligands.length === 0) return null;
  return (
    <AnnotationSection title="Bound ligands" count={ligands.length}>
      <p className="mb-2 text-[10px] leading-relaxed text-zinc-500">
        Residues with a heavy atom within {cutoff} Å of the ligand, measured in this
        file. Not a prediction.
      </p>
      <ul className="space-y-2">
        {ligands.map((ligand) => (
          <li key={`${ligand.chain}-${ligand.auth_seq_id}-${ligand.component}`}>
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-xs text-zinc-200">{ligand.label}</span>
              <span className="ml-auto shrink-0 text-[10px] text-zinc-500">
                {ligand.contacts.length} contact
                {ligand.contacts.length === 1 ? "" : "s"}
              </span>
            </div>
            <div className="mt-1">
              {ligand.contacts.length > 0 ? (
                <ResidueChips residues={ligand.contacts} label={ligand.label} />
              ) : (
                <p className="text-[10px] text-zinc-500">
                  No polymer residue is within {cutoff} Å — this group is not in a
                  pocket of the modelled chains.
                </p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </AnnotationSection>
  );
}

/** The convergence table: curated, observed, or both. */
export function PrioritySection({ residues }: { residues: PriorityResidue[] }) {
  const setSelection = useStore((s) => s.setSelection);
  if (residues.length === 0) return null;
  const both = residues.filter((r) => r.evidence_kinds > 1);

  return (
    <AnnotationSection title="High-priority residues" count={residues.length}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-[10px] leading-relaxed text-zinc-500">
          Ordered by how many independent kinds of evidence converge — a curator and
          this structure, or one of the two. There is no score.
        </p>
        <button
          type="button"
          onClick={() => setSelection(residues.map((r) => r.key))}
          className="shrink-0 rounded border border-dashed border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-400 hover:border-zinc-500 hover:text-zinc-100"
        >
          select all
        </button>
      </div>
      {both.length > 0 && (
        <p className="mb-2 text-[11px] text-emerald-300/90">
          {both.length} residue{both.length === 1 ? " is" : "s are"} both curated by
          UniProt and observed touching a ligand here.
        </p>
      )}
      <ul className="space-y-1.5">
        {residues.map((residue) => (
          <li key={residue.key} className="flex items-start gap-2">
            <ResidueChip residue={residue} />
            <div className="min-w-0 flex-1">
              <ul className="text-[10px] leading-relaxed text-zinc-400">
                {residue.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
            <span
              className="shrink-0 font-mono text-[10px] tabular-nums text-zinc-500"
              title="Kyte-Doolittle hydropathy · formal charge · relative solvent accessibility"
            >
              {residue.hydropathy?.toFixed(1) ?? "—"} /{" "}
              {residue.charge === null
                ? "—"
                : residue.charge > 0
                  ? `+${residue.charge}`
                  : residue.charge}{" "}
              / {residue.relative_accessibility?.toFixed(2) ?? "—"}
            </span>
          </li>
        ))}
      </ul>
    </AnnotationSection>
  );
}
