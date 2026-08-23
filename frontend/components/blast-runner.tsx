"use client";

import { useEffect, useState } from "react";
import { Loader2, RotateCcw, Search } from "lucide-react";
import { useStore } from "@/lib/store";
import { recallJob } from "@/lib/blast-job-memory";
import type { BlastProgram, ChainInfo } from "@/lib/types";
import { BlastProgress } from "@/components/blast-progress";
import { BlastHitsTable } from "@/components/blast-hits-table";

const DATABASES: ReadonlyArray<{ value: string; label: string }> = [
  { value: "uniprotkb", label: "UniProtKB (all)" },
  { value: "uniprotkb_swissprot", label: "UniProtKB/Swiss-Prot (curated)" },
  { value: "uniprotkb_reference_proteomes", label: "Reference proteomes" },
];

const THRESHOLDS: ReadonlyArray<string> = ["1e-10", "1e-3", "1", "10"];

/**
 * Submit + watch one BLAST search (P8).
 *
 * blastp only from this panel: the query is the structure's own protein
 * sequence, so the other three programs would need an input we do not have
 * here. The backend accepts all four (`program`), and a pasted-nucleotide
 * entry point is a follow-up, not a silent omission.
 *
 * On mount the panel asks `localStorage` whether a job was already running for
 * this protein and resumes it. That is what makes navigating away and back —
 * or reloading outright — pick the same search back up rather than starting a
 * second one at EBI.
 */
export function BlastRunner({
  proteinId,
  chains,
}: {
  proteinId: string;
  chains: ChainInfo[];
}) {
  const job = useStore((s) => s.blastJob);
  const jobProteinId = useStore((s) => s.blastProteinId);
  const submitting = useStore((s) => s.blastSubmitting);
  const error = useStore((s) => s.blastError);
  const submitBlast = useStore((s) => s.submitBlast);
  const resumeBlast = useStore((s) => s.resumeBlast);
  const clearBlast = useStore((s) => s.clearBlast);

  const [database, setDatabase] = useState<string>(DATABASES[0].value);
  const [exp, setExp] = useState<string>("1e-3");
  const [chainId, setChainId] = useState<string>("");

  useEffect(() => {
    if (!proteinId) return;
    const remembered = recallJob(proteinId);
    if (remembered) void resumeBlast(proteinId, remembered);
  }, [proteinId, resumeBlast]);

  // A job belonging to a different protein must never be shown here.
  const activeJob = jobProteinId === proteinId ? job : null;
  const program: BlastProgram = "blastp";

  const run = () =>
    void submitBlast(proteinId, {
      protein_id: proteinId,
      chain_id: chainId || undefined,
      program,
      database,
      exp,
    });

  return (
    <div className="flex flex-col gap-3">
      {!activeJob && (
        <>
          <div className="grid grid-cols-2 gap-2">
            {chains.length > 1 && (
              <Select
                label="Chain"
                value={chainId}
                onChange={setChainId}
                options={[
                  { value: "", label: "Longest chain" },
                  ...chains.map((c) => ({
                    value: c.label,
                    label: `${c.label} (${c.residue_count} aa)`,
                  })),
                ]}
              />
            )}
            <Select
              label="Database"
              value={database}
              onChange={setDatabase}
              options={DATABASES}
            />
            <Select
              label="E-value"
              value={exp}
              onChange={setExp}
              options={THRESHOLDS.map((t) => ({ value: t, label: t }))}
            />
          </div>
          <button
            type="button"
            onClick={run}
            disabled={submitting}
            aria-busy={submitting}
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800/70 px-3 py-1.5 text-xs font-medium text-zinc-100 hover:border-zinc-600 hover:bg-zinc-700/70 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <Search className="size-3.5" aria-hidden />
            )}
            {submitting ? "Submitting…" : "Run blastp at EBI"}
          </button>
          <p className="text-[10px] leading-relaxed text-zinc-500">
            Runs against EBI&rsquo;s NCBI BLAST service. Searches usually take 30&nbsp;seconds
            to a few minutes; you can leave this tab and come back.
          </p>
        </>
      )}

      {activeJob && <BlastProgress job={activeJob} />}

      {error && (
        <p
          role="alert"
          className="rounded border border-red-900/70 bg-red-950/40 px-2 py-1.5 text-[11px] text-red-300"
        >
          {error.message}
        </p>
      )}

      {activeJob?.result && <BlastHitsTable result={activeJob.result} />}

      {activeJob?.finished && (
        <button
          type="button"
          onClick={() => clearBlast(proteinId)}
          className="inline-flex items-center justify-center gap-1.5 self-start rounded-md border border-zinc-800 px-2.5 py-1 text-[11px] text-zinc-300 hover:border-zinc-700 hover:bg-zinc-800/60"
        >
          <RotateCcw className="size-3" aria-hidden />
          New search
        </button>
      )}
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: ReadonlyArray<{ value: string; label: string }>;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-zinc-800 bg-zinc-900 px-1.5 py-1 text-[11px] text-zinc-200 focus:border-zinc-600 focus:outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
