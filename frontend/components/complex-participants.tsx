"use client";

import { Outbound } from "@/components/annotation-section";
import { cn } from "@/lib/utils";
import type { ComplexParticipant } from "@/lib/types";

/**
 * The participant + stoichiometry table — the deliverable of P9.
 *
 * A real `<table>` rather than a grid of divs: it is tabular data, screen
 * readers should announce it as such, and the header cells are what make the
 * stoichiometry column legible at all.
 *
 * Two things the table must not do:
 *
 * * Invent a copy number. Roughly two thirds of curated participants carry no
 *   stoichiometry, and rendering that as "1" would state something the
 *   curators did not. An uncurated cell says so.
 * * Bury the protein you are looking at. The row for the open structure is
 *   marked, because the first question this table answers is "where am I in
 *   this complex, and how many copies of me are there?"
 */
export function ParticipantTable({
  participants,
}: {
  participants: ComplexParticipant[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-[11px]">
        <thead>
          <tr className="border-b border-zinc-800 text-[10px] uppercase tracking-wide text-zinc-500">
            <th scope="col" className="py-1 pr-2 font-medium">
              Participant
            </th>
            <th scope="col" className="py-1 pr-2 font-medium">
              Type
            </th>
            <th scope="col" className="py-1 text-right font-medium">
              Copies
            </th>
          </tr>
        </thead>
        <tbody>
          {participants.map((p) => (
            <ParticipantRow key={p.identifier} participant={p} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ParticipantRow({ participant: p }: { participant: ComplexParticipant }) {
  return (
    <tr
      className={cn(
        "border-b border-zinc-900 align-top last:border-b-0",
        p.is_query_protein && "bg-sky-950/30",
      )}
    >
      <th scope="row" className="py-1.5 pr-2 font-normal">
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="font-medium text-zinc-200">{p.name || p.identifier}</span>
          {p.is_query_protein && (
            <span className="rounded bg-sky-900/60 px-1 py-px text-[9px] uppercase tracking-wide text-sky-300">
              This protein
            </span>
          )}
        </span>
        {p.description && (
          <span className="block text-[10px] leading-snug text-zinc-500">
            {p.description}
          </span>
        )}
        <span className="block text-[10px] text-zinc-600">
          <Outbound href={p.url}>{p.identifier}</Outbound>
        </span>
      </th>
      <td className="py-1.5 pr-2 text-zinc-400">{p.interactor_type ?? "—"}</td>
      <td className="py-1.5 text-right tabular-nums text-zinc-300">
        {p.stoichiometry ?? (
          <span className="text-zinc-600" title="Stoichiometry not curated">
            n/a
          </span>
        )}
      </td>
    </tr>
  );
}
