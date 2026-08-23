"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Search } from "lucide-react";

const INPUT_CLASS =
  "h-8 w-full rounded-md border border-zinc-700 bg-zinc-900 px-2 font-mono text-xs text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-500 focus:outline-none";

/**
 * Asks for the two protein ids when `/compare` is opened without both.
 *
 * Ids are the ones the viewer URL carries (`/viewer/{id}`), which is where a
 * user arriving here already is. The path most people should take instead is
 * the search page — one query returns the RCSB experimental entry and the
 * AlphaFold prediction for the same protein, which is A3's headline case — so
 * that link is given equal weight rather than buried.
 */
export function CompareIdForm({
  initialA = "",
  initialB = "",
}: {
  initialA?: string;
  initialB?: string;
}) {
  const router = useRouter();
  const [a, setA] = useState(initialA);
  const [b, setB] = useState(initialB);

  const trimmedA = a.trim();
  const trimmedB = b.trim();
  const ready = trimmedA.length > 0 && trimmedB.length > 0;

  return (
    <div className="flex flex-col gap-4 rounded-md border border-zinc-800 bg-zinc-900/30 p-4">
      <div>
        <h2 className="text-sm font-medium text-zinc-100">
          Choose two structures to compare
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-zinc-500">
          Paste the ids of two proteins already loaded into ProteoLens — the id
          is the last part of a viewer URL, <code>/viewer/&lt;id&gt;</code>. Or
          search a protein name and import both an experimental entry and its
          AlphaFold prediction.
        </p>
      </div>

      <form
        className="flex flex-col gap-2 sm:flex-row sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          if (!ready) return;
          router.push(
            `/compare?a=${encodeURIComponent(trimmedA)}&b=${encodeURIComponent(trimmedB)}`,
          );
        }}
      >
        <label className="flex-1 text-[10px] uppercase tracking-wide text-zinc-500">
          Protein A
          <input
            className={`mt-1 ${INPUT_CLASS}`}
            value={a}
            onChange={(e) => setA(e.target.value)}
            placeholder="e.g. 3f2a9c1e…"
            aria-label="Protein A id"
          />
        </label>
        <label className="flex-1 text-[10px] uppercase tracking-wide text-zinc-500">
          Protein B
          <input
            className={`mt-1 ${INPUT_CLASS}`}
            value={b}
            onChange={(e) => setB(e.target.value)}
            placeholder="e.g. 7b1d4e60…"
            aria-label="Protein B id"
          />
        </label>
        <button
          type="submit"
          disabled={!ready}
          className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800/70 px-3 text-xs font-medium text-zinc-100 transition-colors hover:border-zinc-600 hover:bg-zinc-700/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Compare
          <ArrowRight className="size-3.5" aria-hidden />
        </button>
      </form>

      <Link
        href="/search"
        className="inline-flex items-center gap-1.5 self-start text-xs text-zinc-400 transition-colors hover:text-zinc-100"
      >
        <Search className="size-3.5" aria-hidden />
        Search and import structures
      </Link>
    </div>
  );
}
