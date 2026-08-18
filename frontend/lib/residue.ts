/**
 * Pure helpers for residue identity, classification, and the `A:123` query
 * syntax used by the sequence panel's search box.
 *
 * ## Residue key convention (P4)
 *
 * A residue key is `"<chainLabel>:<position>"` where `position` is the
 * **1-based ordinal of the residue within that chain's one-letter sequence**
 * as returned by the backend parser — NOT the PDB `auth_seq_id`.
 *
 * The sequence panel is the source of truth for that numbering; the Mol*
 * wrapper builds an ordinal <-> model-residue index at load time so a click in
 * either surface resolves to the same key. See `lib/molstar/residue-index.ts`.
 *
 * Nothing here imports React or Mol*, so it is unit-testable in isolation.
 */

export type ResidueClass =
  | "hydrophobic"
  | "polar"
  | "positive"
  | "negative"
  | "other";

/** Standard-20 groupings used for the sequence panel colouring + legend. */
const CLASS_BY_AA: Readonly<Record<string, ResidueClass>> = {
  A: "hydrophobic",
  V: "hydrophobic",
  L: "hydrophobic",
  I: "hydrophobic",
  M: "hydrophobic",
  F: "hydrophobic",
  W: "hydrophobic",
  P: "hydrophobic",
  S: "polar",
  T: "polar",
  N: "polar",
  Q: "polar",
  G: "polar",
  C: "polar",
  Y: "polar",
  K: "positive",
  R: "positive",
  H: "positive",
  D: "negative",
  E: "negative",
};

/**
 * Maps a one-letter amino-acid code to its class. Unknown codes — including
 * the parser's `X` placeholder for non-standard residues — map to `"other"`.
 */
export function residueClass(aa: string): ResidueClass {
  if (aa.length !== 1) return "other";
  return CLASS_BY_AA[aa.toUpperCase()] ?? "other";
}

export const RESIDUE_CLASS_LABEL: Readonly<Record<ResidueClass, string>> = {
  hydrophobic: "Hydrophobic",
  polar: "Polar",
  positive: "Positive",
  negative: "Negative",
  other: "Other",
};

/** Tailwind text colours, tuned for contrast on the zinc-950 rail. */
export const RESIDUE_CLASS_TEXT: Readonly<Record<ResidueClass, string>> = {
  hydrophobic: "text-amber-300",
  polar: "text-emerald-300",
  positive: "text-sky-300",
  negative: "text-rose-300",
  other: "text-zinc-500",
};

/** Matching swatch backgrounds for the legend. */
export const RESIDUE_CLASS_SWATCH: Readonly<Record<ResidueClass, string>> = {
  hydrophobic: "bg-amber-300",
  polar: "bg-emerald-300",
  positive: "bg-sky-300",
  negative: "bg-rose-300",
  other: "bg-zinc-500",
};

export const RESIDUE_CLASS_ORDER: readonly ResidueClass[] = [
  "hydrophobic",
  "polar",
  "positive",
  "negative",
  "other",
];

/** Builds the canonical key for a 1-based ordinal position within a chain. */
export function residueKey(chainLabel: string, position: number): string {
  return `${chainLabel}:${position}`;
}

/** Inverse of {@link residueKey}. Returns `null` for anything malformed. */
export function parseResidueKey(
  key: string,
): { chain: string; position: number } | null {
  const idx = key.indexOf(":");
  if (idx <= 0 || idx === key.length - 1) return null;
  const chain = key.slice(0, idx);
  const rest = key.slice(idx + 1);
  if (!/^\d+$/.test(rest)) return null;
  const position = Number(rest);
  if (!Number.isInteger(position) || position < 1) return null;
  return { chain, position };
}

/** Minimal shape of `ChainInfo` the query parser needs. */
export interface QueryChain {
  label: string;
  residue_count: number;
}

/**
 * Compares the residue counts Mol* derived from the structure file against the
 * counts the API reported, and returns one human-readable line per chain that
 * disagrees. An empty array means the two numbering schemes are in lockstep and
 * every `"chain:position"` key round-trips.
 *
 * Lives here (rather than next to the Mol* index it checks) so it stays free of
 * Mol* imports and testable on a plain map.
 */
export function findIndexDrift(
  index: { readonly chainCounts: ReadonlyMap<string, number> },
  chains: readonly QueryChain[],
): string[] {
  const drift: string[] = [];
  for (const chain of chains) {
    const actual = index.chainCounts.get(chain.label);
    if (actual === undefined) {
      drift.push(`chain ${chain.label}: absent from the loaded structure`);
    } else if (actual !== chain.residue_count) {
      drift.push(
        `chain ${chain.label}: Mol* has ${actual} residues, API reported ${chain.residue_count}`,
      );
    }
  }
  return drift;
}

export type ResidueQueryResult =
  | { ok: true; key: string; chain: string; position: number }
  | { ok: false; error: string };

const QUERY_RE = /^([A-Za-z0-9]+)\s*:\s*(\d+)$/;

/**
 * Parses the sequence panel's `A:123` search syntax.
 *
 * Accepts surrounding whitespace and a lowercase chain letter (matched
 * case-insensitively only when no exact-case chain exists — PDB files may
 * legitimately contain both `A` and `a`). `123` is the 1-based position within
 * the chain's sequence, i.e. the same numbering the sequence panel renders.
 */
export function parseResidueQuery(
  input: string,
  chains: readonly QueryChain[],
): ResidueQueryResult {
  const trimmed = input.trim();
  if (trimmed.length === 0) {
    return { ok: false, error: "Enter a residue such as A:12" };
  }

  const m = QUERY_RE.exec(trimmed);
  if (!m) {
    return { ok: false, error: `Could not read "${trimmed}" — use chain:residue, e.g. A:12` };
  }

  const rawChain = m[1];
  const position = Number(m[2]);

  const chain =
    chains.find((c) => c.label === rawChain) ??
    chains.find((c) => c.label.toLowerCase() === rawChain.toLowerCase());

  if (!chain) {
    const available = chains.map((c) => c.label).join(", ");
    return {
      ok: false,
      error: available
        ? `No chain ${rawChain} — available: ${available}`
        : `No chain ${rawChain} — this structure has no chains`,
    };
  }

  if (position < 1 || position > chain.residue_count) {
    return {
      ok: false,
      error: `No residue ${chain.label}:${position} — chain ${chain.label} has ${chain.residue_count} residues`,
    };
  }

  return {
    ok: true,
    key: residueKey(chain.label, position),
    chain: chain.label,
    position,
  };
}
