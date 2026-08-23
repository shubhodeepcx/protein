"use client";

import { ExternalLink, Loader2, Star } from "lucide-react";
import type { SimilarProteinsResponse } from "@/lib/types";
import { formatCount } from "@/lib/blast-format";
import { useProteinImport } from "@/lib/use-protein-import";

/**
 * UniRef homologs (P8) — the instant half of the Similarity tab.
 *
 * UniRef is a clustering UniProt has already computed, so this list is there
 * the moment the tab opens, while a BLAST search is still queueing. Same
 * "Open" affordance as the BLAST table, through the same import hook.
 */
export function SimilarProteinsSection({ data }: { data: SimilarProteinsResponse }) {
  const { importingId, error, open } = useProteinImport();

  if (!data.accession_resolved) {
    return (
      <p className="text-[11px] leading-relaxed text-zinc-500">{data.resolution_note}</p>
    );
  }

  if (data.members.length === 0) {
    return (
      <p className="text-[11px] leading-relaxed text-zinc-500">
        {data.resolution_note}
      </p>
    );
  }

  const level = Math.round(data.identity_threshold * 100);

  return (
    <div className="flex flex-col gap-2">
      <p className="text-[10px] leading-relaxed text-zinc-500">
        {data.cluster_name ?? data.cluster_id} &middot; UniRef{level}, meaning members
        share at least {level}% sequence identity. Showing{" "}
        {data.members.length} of {formatCount(data.member_count)} cluster members
        {data.truncated ? " (the rest are not shown)" : ""}.
      </p>

      {error && (
        <p
          role="alert"
          className="rounded border border-red-900/70 bg-red-950/40 px-2 py-1.5 text-[11px] text-red-300"
        >
          {error}
        </p>
      )}

      <ul data-testid="similar-list" className="flex flex-col">
        {data.members.map((member) => {
          const busy = importingId === member.accession;
          return (
            <li
              key={member.accession}
              data-testid={`similar-${member.accession}`}
              className="flex items-start gap-2 border-b border-zinc-900 py-1.5 last:border-b-0"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  {member.uniprot_url ? (
                    <a
                      href={member.uniprot_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-1 font-mono text-[11px] text-sky-400 hover:underline"
                    >
                      {member.accession}
                      <ExternalLink className="size-2.5 shrink-0" aria-hidden />
                    </a>
                  ) : (
                    <span className="font-mono text-[11px] text-zinc-300">
                      {member.accession}
                    </span>
                  )}
                  {member.is_representative && (
                    <span
                      title="Cluster representative sequence"
                      className="inline-flex items-center gap-0.5 rounded border border-amber-900/70 px-1 text-[9px] uppercase tracking-wide text-amber-400"
                    >
                      <Star className="size-2" aria-hidden />
                      rep
                    </span>
                  )}
                  {member.sequence_length !== null && (
                    <span className="text-[10px] text-zinc-600">
                      {member.sequence_length} aa
                    </span>
                  )}
                </div>
                <p className="truncate text-[11px] text-zinc-300">
                  {member.protein_name ?? member.entry_id ?? "Unnamed entry"}
                </p>
                {member.organism && (
                  <p className="truncate text-[10px] italic text-zinc-500">
                    {member.organism}
                  </p>
                )}
              </div>

              <button
                type="button"
                onClick={() => void open(member.accession)}
                disabled={importingId !== null}
                aria-busy={busy}
                aria-label={`Open ${member.accession} in the viewer`}
                className="mt-0.5 inline-flex shrink-0 items-center gap-1 rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/70 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy && <Loader2 className="size-2.5 animate-spin" aria-hidden />}
                {busy ? "Opening…" : "Open"}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
