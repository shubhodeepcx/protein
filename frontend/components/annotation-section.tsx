"use client";

import { useState, type ReactNode } from "react";
import { ChevronRight, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * One collapsible section of the annotation panel.
 *
 * Sections start expanded: the complaint P6 answers is an interface that looks
 * empty, and ten collapsed headings look emptier than nine. Collapsing is for
 * getting a long section out of the way, not the default state.
 *
 * The panel only ever mounts a section that has data — "render it collapsed"
 * is not a substitute for not rendering it at all.
 */
export function AnnotationSection({
  title,
  count,
  defaultOpen = true,
  children,
}: {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="border-b border-zinc-800">
      <h3>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-zinc-900/60"
        >
          <ChevronRight
            className={cn(
              "size-3 shrink-0 text-zinc-500 transition-transform",
              open && "rotate-90",
            )}
            aria-hidden
          />
          <span className="text-[10px] font-semibold uppercase tracking-wide text-zinc-300">
            {title}
          </span>
          {count !== undefined && (
            <span className="ml-auto text-[10px] tabular-nums text-zinc-500">
              {count}
            </span>
          )}
        </button>
      </h3>
      {open && <div className="px-3 pb-3">{children}</div>}
    </section>
  );
}

/**
 * An outbound link, or plain text when there is no URL to link to.
 *
 * `href === null` is the normal case for an identifier whose database we hold
 * no template for; showing the id unlinked beats showing a dead link.
 */
export function Outbound({
  href,
  children,
}: {
  href: string | null;
  children: ReactNode;
}) {
  if (!href) return <span className="text-zinc-300">{children}</span>;
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="inline-flex items-center gap-1 text-sky-400 hover:text-sky-300 hover:underline"
    >
      {children}
      <ExternalLink className="size-2.5 shrink-0" aria-hidden />
    </a>
  );
}

/** A small labelled pill — keywords, gene names, lineage steps. */
export function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="rounded border border-zinc-800 bg-zinc-900/60 px-1.5 py-0.5 text-[11px] text-zinc-300">
      {children}
    </span>
  );
}

/** A label/value row, mirroring the Overview tab's field layout. */
export function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="shrink-0 text-[10px] uppercase tracking-wide text-zinc-500">
        {label}
      </span>
      <span className="text-right text-xs text-zinc-200">{value}</span>
    </div>
  );
}
