"use client";

import { AlertCircle, CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import type { BlastJobStatus } from "@/lib/types";
import { formatElapsed } from "@/lib/blast-format";

/**
 * Progress feedback for a running BLAST search (P8).
 *
 * A BLAST job takes 30 s to several minutes. An indeterminate spinner over
 * that long reads as "hung", so this shows the three facts that distinguish a
 * slow job from a dead one: what EBI says the job is doing, how long it has
 * actually been running, and the job id — which is what the user needs if they
 * ever want to ask EBI about it directly.
 *
 * The bar is deliberately NOT a percentage. BLAST publishes no completion
 * fraction, and inventing one would be a lie that gets less true the longer
 * the job runs.
 */
export function BlastProgress({ job }: { job: BlastJobStatus }) {
  const tone = statusTone(job.status);

  return (
    <div
      data-testid="blast-progress"
      role="status"
      aria-live="polite"
      className="rounded-md border border-zinc-800 bg-zinc-900/40 p-3"
    >
      <div className="flex items-center gap-2">
        <tone.Icon
          className={`size-4 shrink-0 ${tone.className} ${tone.spin ? "animate-spin" : ""}`}
          aria-hidden
        />
        <span className="text-xs font-medium text-zinc-200">{tone.label}</span>
        {!job.finished && (
          <span className="ml-auto inline-flex items-center gap-1 text-[11px] tabular-nums text-zinc-400">
            <Clock className="size-3" aria-hidden />
            {formatElapsed(job.elapsed_seconds)}
          </span>
        )}
      </div>

      <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-400">{job.message}</p>

      {!job.finished && (
        <div
          className="mt-2 h-1 overflow-hidden rounded-full bg-zinc-800"
          role="presentation"
        >
          {/* Indeterminate on purpose — BLAST reports no completion fraction. */}
          <div className="h-full w-1/3 animate-pulse rounded-full bg-sky-600" />
        </div>
      )}

      <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] text-zinc-500">
        <Fact label="Program" value={job.program} />
        <Fact label="Database" value={job.database} />
        <Fact label="Query" value={`${job.query_source} · ${job.query_length} aa`} />
        <Fact label="Job" value={job.job_id} mono />
      </dl>
    </div>
  );
}

function Fact({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex min-w-0 items-baseline gap-1.5">
      <dt className="shrink-0 uppercase tracking-wide">{label}</dt>
      <dd className={`min-w-0 truncate text-zinc-400 ${mono ? "font-mono" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

function statusTone(status: BlastJobStatus["status"]) {
  switch (status) {
    case "FINISHED":
      return {
        Icon: CheckCircle2,
        className: "text-emerald-400",
        label: "Search complete",
        spin: false,
      };
    case "FAILURE":
    case "ERROR":
      return { Icon: XCircle, className: "text-red-400", label: "Search failed", spin: false };
    case "NOT_FOUND":
      return {
        Icon: AlertCircle,
        className: "text-amber-400",
        label: "Job expired",
        spin: false,
      };
    case "QUEUED":
      return { Icon: Loader2, className: "text-sky-400", label: "Queued", spin: true };
    default:
      return { Icon: Loader2, className: "text-sky-400", label: "Running", spin: true };
  }
}
