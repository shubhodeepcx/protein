"use client";

import { AnnotationSection } from "@/components/annotation-section";
import { ResidueChips } from "@/components/functional-residues";
import { cn } from "@/lib/utils";
import type {
  CompoundCategory,
  CompoundGroup,
  CompoundInstance,
  NucleicAcidChain,
} from "@/lib/types";

/**
 * The sections of the Compounds tab. Contact residues reuse A5's
 * `ResidueChips`, so a click selects in 3D through the existing
 * `setSelection` path; there is no second selection mechanism.
 */

export const CATEGORY_META: Record<
  CompoundCategory,
  { title: string; badge: string; blurb: string }
> = {
  ligand: {
    title: "Ligands",
    badge: "border-violet-500/40 bg-violet-500/10 text-violet-300",
    blurb: "Small molecules bound to the protein: substrates, inhibitors, drugs.",
  },
  cofactor: {
    title: "Cofactors & nucleotides",
    badge: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    blurb: "Hemes, flavins, NAD(P), ATP/GTP and other groups enzymes need to work.",
  },
  ion: {
    title: "Ions",
    badge: "border-cyan-500/40 bg-cyan-500/10 text-cyan-300",
    blurb: "Metal and halide ions, often structural or catalytic.",
  },
  carbohydrate: {
    title: "Carbohydrates",
    badge: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
    blurb: "Sugars and glycans, including glycosylation on the protein surface.",
  },
  free_amino_acid: {
    title: "Free amino acids",
    badge: "border-rose-500/40 bg-rose-500/10 text-rose-300",
    blurb: "Amino acids bound as molecules in their own right, not part of a chain.",
  },
  modified_residue: {
    title: "Modified residues",
    badge: "border-sky-500/40 bg-sky-500/10 text-sky-300",
    blurb: "Residues inside the protein chain carrying a modification (e.g. phosphorylation).",
  },
  additive: {
    title: "Additives",
    badge: "border-zinc-600 bg-zinc-800/60 text-zinc-400",
    blurb: "Crystallisation, cryoprotectant or buffer components.",
  },
};

function instanceLabel(code: string, instance: CompoundInstance): string {
  const number =
    instance.auth_seq_id === null
      ? ""
      : ` ${instance.auth_seq_id}${instance.insertion_code ?? ""}`;
  return `${code}${number} (chain ${instance.chain})`;
}

function GroupCard({ group }: { group: CompoundGroup }) {
  const meta = CATEGORY_META[group.category];
  return (
    <li className="rounded-md border border-zinc-800 bg-zinc-900/30 px-2.5 py-2">
      <div className="flex items-baseline gap-2">
        <span
          className={cn("rounded border px-1.5 py-0.5 font-mono text-[10px]", meta.badge)}
        >
          {group.code}
        </span>
        <span className="min-w-0 flex-1 truncate text-xs text-zinc-200" title={group.name ?? ""}>
          {group.name ?? "Unnamed component"}
        </span>
        <span className="shrink-0 text-[10px] tabular-nums text-zinc-500">
          ×{group.instances.length}
        </span>
      </div>
      {(group.formula || group.formula_weight !== null || group.parent_residue) && (
        <p className="mt-1 text-[10px] text-zinc-500">
          {group.formula && <span className="font-mono">{group.formula}</span>}
          {group.formula_weight !== null && (
            <span> · {group.formula_weight.toFixed(1)} Da</span>
          )}
          {group.parent_residue && <span> · derived from {group.parent_residue}</span>}
        </p>
      )}
      <ul className="mt-1.5 space-y-1.5">
        {group.instances.map((instance) => {
          const label = instanceLabel(group.code, instance);
          return (
            <li key={label}>
              <div className="text-[10px] text-zinc-400">
                {label} · {instance.atom_count} atom{instance.atom_count === 1 ? "" : "s"}
                {group.category !== "modified_residue" && (
                  <span>
                    {" "}
                    · {instance.contacts.length} contact
                    {instance.contacts.length === 1 ? "" : "s"}
                  </span>
                )}
              </div>
              {instance.contacts.length > 0 && (
                <div className="mt-1">
                  <ResidueChips residues={instance.contacts} label={label} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </li>
  );
}

/** One section per category, groups in the order the backend ranked them. */
export function CompoundCategorySection({
  category,
  groups,
}: {
  category: CompoundCategory;
  groups: CompoundGroup[];
}) {
  if (groups.length === 0) return null;
  const meta = CATEGORY_META[category];
  return (
    <AnnotationSection
      title={meta.title}
      count={groups.length}
      defaultOpen={category !== "additive"}
    >
      <p className="mb-2 text-[10px] text-zinc-500">{meta.blurb}</p>
      <ul className="space-y-2">
        {groups.map((group) => (
          <GroupCard key={`${group.category}-${group.code}`} group={group} />
        ))}
      </ul>
    </AnnotationSection>
  );
}

/** DNA / RNA strands and the protein residues that touch them. */
export function NucleicAcidSection({ chains }: { chains: NucleicAcidChain[] }) {
  if (chains.length === 0) return null;
  return (
    <AnnotationSection title="Nucleic acids" count={chains.length}>
      <p className="mb-2 text-[10px] text-zinc-500">
        DNA and RNA strands in the file. Contact residues form the protein&apos;s
        nucleic-acid-binding interface.
      </p>
      <ul className="space-y-2">
        {chains.map((chain) => (
          <li
            key={chain.label}
            className="rounded-md border border-zinc-800 bg-zinc-900/30 px-2.5 py-2"
          >
            <div className="flex items-baseline gap-2 text-xs">
              <span className="rounded border border-orange-500/40 bg-orange-500/10 px-1.5 py-0.5 font-mono text-[10px] text-orange-300">
                {chain.kind}
              </span>
              <span className="text-zinc-200">Chain {chain.label}</span>
              <span className="ml-auto text-[10px] tabular-nums text-zinc-500">
                {chain.length} nt
                {chain.gc_fraction !== null &&
                  ` · GC ${(chain.gc_fraction * 100).toFixed(0)}%`}
              </span>
            </div>
            <p
              className="mt-1 break-all font-mono text-[10px] leading-relaxed text-zinc-400"
              data-testid={`nucleic-sequence-${chain.label}`}
            >
              {chain.sequence}
            </p>
            <div className="mt-1.5 text-[10px] text-zinc-400">
              {chain.contacts.length} protein contact
              {chain.contacts.length === 1 ? "" : "s"}
            </div>
            {chain.contacts.length > 0 && (
              <div className="mt-1">
                <ResidueChips residues={chain.contacts} label={`chain ${chain.label}`} />
              </div>
            )}
          </li>
        ))}
      </ul>
    </AnnotationSection>
  );
}
