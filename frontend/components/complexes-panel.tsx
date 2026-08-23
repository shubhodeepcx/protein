"use client";

import { useEffect, useState } from "react";
import { Loader2, AlertCircle, Info } from "lucide-react";
import { useStore } from "@/lib/store";
import { AnnotationSection, Field, Outbound } from "@/components/annotation-section";
import { ParticipantTable } from "@/components/complex-participants";
import type { ProteinComplex, ProteinComplexes } from "@/lib/types";

/**
 * Complexes tab: macromolecular complexes from the EBI Complex Portal (P9).
 *
 * Answers the client's "complex viewer … show the functions … encoded in which
 * component, protein names, gene names" with the data tier: the curated
 * function of the complex, and a participant table with stoichiometry.
 *
 * A protein belonging to no complex is a successful, empty response and gets an
 * explanation, exactly as the Annotations tab does — nothing is broken, there
 * is simply nothing to show.
 */
export function ComplexesPanel({ proteinId }: { proteinId: string }) {
  const complexes = useStore((s) => s.complexes);
  const loading = useStore((s) => s.complexesLoading);
  const error = useStore((s) => s.complexesError);
  const loadComplexes = useStore((s) => s.loadComplexes);
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    if (!proteinId) return;
    void loadComplexes(proteinId);
  }, [proteinId, loadComplexes]);

  // A new payload can be shorter than the last one; never hold an index past
  // the end of the list.
  const list = complexes?.complexes ?? [];
  const index = selected < list.length ? selected : 0;

  if (loading && !complexes) {
    return (
      <div className="flex h-full items-center justify-center text-zinc-500">
        <Loader2 className="size-5 animate-spin" aria-hidden />
        <span className="ml-2 text-xs">Fetching complexes&hellip;</span>
      </div>
    );
  }

  if (error && !complexes) {
    return (
      <div
        role="alert"
        className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center"
      >
        <AlertCircle className="size-6 text-red-400" aria-hidden />
        <p className="text-xs text-red-400">Complexes failed: {error.message}</p>
      </div>
    );
  }

  if (!complexes) {
    return (
      <div className="flex h-full items-center justify-center px-4 text-center">
        <p className="text-xs text-zinc-500">Load a protein to see its complexes.</p>
      </div>
    );
  }

  if (list.length === 0) return <NoComplexes payload={complexes} />;

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      {list.length > 1 && (
        <ComplexSelector list={list} index={index} onSelect={setSelected} />
      )}
      <ComplexDetail complex={list[index]} />
      <p className="px-3 py-3 text-[10px] leading-relaxed text-zinc-600">
        Complex data from the EBI Complex Portal.{" "}
        {complexes.search_matches > list.length &&
          `${complexes.search_matches - list.length} further record(s) name this accession in their description without containing the protein, and are not listed.`}
      </p>
    </div>
  );
}

/** Why the tab is empty — an accession that resolved, or one that did not. */
function NoComplexes({ payload }: { payload: ProteinComplexes }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
      <Info className="size-5 text-zinc-500" aria-hidden />
      <p className="text-xs text-zinc-400">
        {payload.accession_resolved
          ? "No Complex Portal complex contains this protein."
          : "No complexes for this structure."}
      </p>
      <p className="text-[11px] leading-relaxed text-zinc-500">
        {payload.resolution_note}
      </p>
    </div>
  );
}

/**
 * The pulldown for a protein that belongs to several complexes.
 *
 * A native `<select>`: it is one of the few controls that is keyboard- and
 * screen-reader-correct with no work, and the list is short.
 */
function ComplexSelector({
  list,
  index,
  onSelect,
}: {
  list: ProteinComplex[];
  index: number;
  onSelect: (i: number) => void;
}) {
  return (
    <div className="flex items-center gap-2 border-b border-zinc-800 px-3 py-2">
      <label
        htmlFor="complex-select"
        className="shrink-0 text-[10px] uppercase tracking-wide text-zinc-500"
      >
        Complex
      </label>
      <select
        id="complex-select"
        value={index}
        onChange={(e) => onSelect(Number(e.target.value))}
        className="min-w-0 flex-1 truncate rounded border border-zinc-800 bg-zinc-900 px-2 py-1 text-xs text-zinc-200"
      >
        {list.map((c, i) => (
          <option key={c.accession} value={i}>
            {c.name || c.accession}
            {c.predicted ? " (predicted)" : ""}
          </option>
        ))}
      </select>
      <span className="shrink-0 text-[10px] tabular-nums text-zinc-500">
        {index + 1}/{list.length}
      </span>
    </div>
  );
}

function ComplexDetail({ complex }: { complex: ProteinComplex }) {
  return (
    <>
      <AnnotationSection title="Complex">
        <Field
          label="Name"
          value={<span className="font-medium">{complex.name || complex.accession}</span>}
        />
        <Field
          label="Accession"
          value={<Outbound href={complex.url}>{complex.accession}</Outbound>}
        />
        {complex.organism && <Field label="Organism" value={complex.organism} />}
        {/* A predicted complex is a computational inference, not curated
            experimental evidence. Presenting the two identically would dress a
            prediction up as knowledge. */}
        {complex.predicted && (
          <Field
            label="Evidence"
            value={<span className="text-amber-400">Predicted, not curated</span>}
          />
        )}
      </AnnotationSection>

      {complex.description && (
        <AnnotationSection title="Function">
          <p className="text-xs leading-relaxed text-zinc-300">{complex.description}</p>
        </AnnotationSection>
      )}

      <AnnotationSection title="Participants" count={complex.participants.length}>
        <ParticipantTable participants={complex.participants} />
      </AnnotationSection>
    </>
  );
}
