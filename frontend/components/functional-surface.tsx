"use client";

import { AnnotationSection } from "@/components/annotation-section";
import type { ChainMapping, SurfaceProfile } from "@/lib/types";

/**
 * The two sections that describe the *whole chain* rather than a site:
 * surface hydrophobicity and charge, and the position mapping the curated
 * sections were placed through.
 *
 * The mapping section is published rather than kept internal on purpose. A
 * curated position placed on the wrong residue is the worst thing this feature
 * can do, so the evidence for every placement is on the screen and a refusal
 * says which chain it refused and why.
 */

/** Surface hydrophobicity and charge, per chain. */
export function SurfaceSection({
  profiles,
  note,
}: {
  profiles: SurfaceProfile[];
  note: string;
}) {
  if (profiles.length === 0) return null;
  return (
    <AnnotationSection title="Surface hydrophobicity and charge" count={profiles.length}>
      <table className="w-full text-[11px] tabular-nums">
        <thead>
          <tr className="text-[10px] uppercase tracking-wide text-zinc-500">
            <th className="py-1 text-left font-normal">Chain</th>
            <th className="py-1 text-right font-normal">Net charge</th>
            <th className="py-1 text-right font-normal">Surface charge</th>
            <th className="py-1 text-right font-normal">Mean KD</th>
            <th className="py-1 text-right font-normal">Surface KD</th>
          </tr>
        </thead>
        <tbody className="text-zinc-300">
          {profiles.map((profile) => (
            <tr key={profile.chain} className="border-t border-zinc-800/60">
              <td className="py-1 text-left font-mono">{profile.chain}</td>
              <td className="py-1 text-right">{signed(profile.net_charge)}</td>
              <td className="py-1 text-right">
                {profile.surface_net_charge === null
                  ? "—"
                  : signed(profile.surface_net_charge)}
              </td>
              <td className="py-1 text-right">{profile.mean_hydropathy.toFixed(2)}</td>
              <td className="py-1 text-right">
                {profile.surface_mean_hydropathy?.toFixed(2) ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[10px] leading-relaxed text-zinc-500">
        {note} Histidine is counted apart from the charge: its side-chain pKa sits near
        neutral, so calling it positive at pH 7 would overstate it.
      </p>
    </AnnotationSection>
  );
}

function signed(value: number): string {
  return value > 0 ? `+${value}` : String(value);
}

/** How UniProt positions were related to this file's residues — or were not. */
export function MappingSection({ mappings }: { mappings: ChainMapping[] }) {
  if (mappings.length === 0) return null;
  return (
    <AnnotationSection title="UniProt position mapping" count={mappings.length} defaultOpen={false}>
      <p className="mb-2 text-[10px] leading-relaxed text-zinc-500">
        A UniProt sequence position is not a residue number. Each chain is aligned to
        the UniProt sequence and positions are read through that alignment; a chain
        the alignment does not support is refused rather than guessed at.
      </p>
      <ul className="space-y-1.5">
        {mappings.map((mapping) => (
          <li key={mapping.chain} className="text-[11px] leading-relaxed">
            <span className="font-mono text-zinc-200">Chain {mapping.chain}</span>{" "}
            <span className={mapping.mapped ? "text-emerald-400" : "text-amber-400"}>
              {mapping.mapped ? "mapped" : "not mapped"}
            </span>{" "}
            <span className="text-zinc-500">
              ({mapping.identity_percent}% identity over {mapping.aligned_columns}{" "}
              aligned columns)
            </span>
            <p className="text-[10px] text-zinc-400">
              {mapping.mapped ? mapping.offset_note : mapping.note}
            </p>
          </li>
        ))}
      </ul>
    </AnnotationSection>
  );
}
