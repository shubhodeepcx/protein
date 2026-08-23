/**
 * Splits a pairwise alignment into fixed-width blocks with residue numbering,
 * the way EMBOSS `needle` and BLAST lay one out.
 *
 * Pure and framework-free so the numbering can be tested directly — it is the
 * part a reader actually relies on ("which residue is this mismatch?"), and it
 * is easy to get subtly wrong, because a row's position counter must advance on
 * residues only and never on gap characters.
 */

export const GAP = "-";

export interface AlignmentBlock {
  /** 0-based column index this block starts at, for a stable React key. */
  column: number;
  rowA: string;
  match: string;
  rowB: string;
  /** 1-based position of this block's first residue on that row, null if all gaps. */
  startA: number | null;
  endA: number | null;
  startB: number | null;
  endB: number | null;
}

function countResidues(row: string): number {
  let total = 0;
  for (const char of row) if (char !== GAP) total += 1;
  return total;
}

/**
 * `aligned_a` / `match_line` / `aligned_b` cut into blocks of `width` columns.
 *
 * Each block reports the 1-based residue range it covers on each row. A block
 * whose row is entirely gaps reports `null` for both ends rather than repeating
 * the neighbouring position, so a long insertion cannot look like it occupies
 * residues that are not there.
 *
 * Rows shorter than `aligned_a` (which should not happen — the backend emits
 * three equal-length strings) are simply padded out to the block width, so a
 * malformed payload renders short instead of throwing.
 */
export function alignmentBlocks(
  alignedA: string,
  matchLine: string,
  alignedB: string,
  width = 60,
): AlignmentBlock[] {
  if (width < 1 || alignedA.length === 0) return [];

  const blocks: AlignmentBlock[] = [];
  // Residues consumed on each row BEFORE the current block.
  let consumedA = 0;
  let consumedB = 0;

  for (let column = 0; column < alignedA.length; column += width) {
    const rowA = alignedA.slice(column, column + width);
    const rowB = alignedB.slice(column, column + width);
    const match = matchLine.slice(column, column + width);

    const residuesA = countResidues(rowA);
    const residuesB = countResidues(rowB);

    blocks.push({
      column,
      rowA,
      match,
      rowB,
      startA: residuesA > 0 ? consumedA + 1 : null,
      endA: residuesA > 0 ? consumedA + residuesA : null,
      startB: residuesB > 0 ? consumedB + 1 : null,
      endB: residuesB > 0 ? consumedB + residuesB : null,
    });

    consumedA += residuesA;
    consumedB += residuesB;
  }

  return blocks;
}

/** Total residues on a row — exported so callers can assert against the API's counts. */
export function residueCount(row: string): number {
  return countResidues(row);
}
