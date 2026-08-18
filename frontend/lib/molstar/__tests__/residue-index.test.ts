/**
 * The Mol*-facing half of the residue-ordinal mirror, against real structures.
 *
 * ## Why this exists
 *
 * `lib/__tests__/residue-map.test.ts` pins the numbering logic against
 * hand-built `ResidueRecord` fixtures. That proves the arithmetic, but it
 * cannot prove the step before it: that `extractResidueRecords` reads the right
 * fields out of a real Mol* hierarchy, and that the filter it applies is the
 * same one `backend/app/services/parser.py` applies. Those hand-built records
 * assume Mol* re-sorts atoms on load; nothing demonstrated that it does.
 *
 * So this module loads the **same two fixture files the backend parity test
 * uses** — `backend/tests/fixtures/parity_multichain.{pdb,cif}`, one structure
 * written in both formats — runs Mol*'s real parsers over them, and asserts the
 * index it builds matches the sequences the backend reports for those files.
 * Testing against the identical bytes is the point: it is the only way the two
 * halves of the mirror can be shown to agree rather than assumed to.
 *
 * This is not a test of Mol* (AGENTS.md: Mol* is a trusted library). It is a
 * test of our adapter over it, and of the seam P4 and P5 meet at: P4 built the
 * mirror against `PDBParser`, P5 started feeding it mmCIF from RCSB.
 *
 * Only Mol*'s parsing layer is exercised — no plugin, no canvas, no WebGL —
 * which is why this runs in jsdom. Rendering and click delivery still need the
 * browser-level coverage tracked in PROJECT_TRACKER.md.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { CIF } from "molstar/lib/mol-io/reader/cif";
import { parsePDB } from "molstar/lib/mol-io/reader/pdb/parser";
import { trajectoryFromMmCIF } from "molstar/lib/mol-model-formats/structure/mmcif";
import { trajectoryFromPDB } from "molstar/lib/mol-model-formats/structure/pdb";
import { Structure, StructureElement } from "molstar/lib/mol-model/structure";
import { Task } from "molstar/lib/mol-task";
import {
  buildResidueIndex,
  extractResidueRecords,
  keysToLoci,
  resolveResidueLocus,
  findIndexDrift,
  type ResidueIndexMap,
} from "@/lib/molstar/residue-index";

const FIXTURES = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../backend/tests/fixtures",
);

/**
 * The numbering `backend/tests/test_parser_parity.py` pins for these files.
 * Kept as three-letter codes because that is what the hierarchy stores; the
 * backend's one-letter sequences are TAGSK / VCWP / GTASK.
 *
 * Chain H is modelled from author residue 27 with a gap and an insertion code,
 * and carries an MSE coded HETATM inside the polymer. Chain M lists its
 * residues out of `label_seq_id` order. Neither may disturb the ordinals.
 *
 * The author names the chains H, L and M while the mmCIF labels them A, B and
 * C — so a mirror that read `label_asym_id` would produce entirely different
 * keys for the imported copy of the very same structure.
 */
const EXPECTED: Readonly<Record<string, readonly string[]>> = {
  H: ["THR", "ALA", "GLY", "SER", "LYS"],
  L: ["VAL", "CYS", "TRP", "PRO"],
  M: ["GLY", "THR", "ALA", "SER", "LYS"],
};

async function loadStructure(file: string): Promise<Structure> {
  const text = readFileSync(resolve(FIXTURES, file), "utf8");

  if (file.endsWith(".cif")) {
    const parsed = await CIF.parse(text).run();
    if (parsed.isError) throw new Error(parsed.message);
    const trajectory = await trajectoryFromMmCIF(parsed.result.blocks[0]).run();
    return Structure.ofModel(
      await Task.resolveInContext(trajectory.getFrameAtIndex(0)),
    );
  }

  const parsed = await parsePDB(text).run();
  if (parsed.isError) throw new Error(parsed.message);
  const trajectory = await trajectoryFromPDB(parsed.result).run();
  return Structure.ofModel(
    await Task.resolveInContext(trajectory.getFrameAtIndex(0)),
  );
}

/** The three-letter code of the residue a model residue index names. */
function residueName(structure: Structure, residue: number): string {
  const h = structure.models[0].atomicHierarchy;
  return String(
    h.atoms.label_comp_id.value(h.residueAtomSegments.offsets[residue]),
  );
}

/** `{ A: ["THR", ...] }` — what the index says residue A:1, A:2 ... are. */
function chainsFromIndex(
  structure: Structure,
  index: ResidueIndexMap,
): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const [label, count] of index.chainCounts) {
    out[label] = Array.from({ length: count }, (_, i) => {
      const residue = index.keyToResidue.get(`${label}:${i + 1}`);
      if (residue === undefined) throw new Error(`missing key ${label}:${i + 1}`);
      return residueName(structure, residue);
    });
  }
  return out;
}

const FORMATS = [
  ["pdb", "parity_multichain.pdb"],
  ["mmcif", "parity_multichain.cif"],
] as const;

describe.each(FORMATS)("residue index from %s", (_format, file) => {
  it("numbers each chain 1..n in file order, matching the backend", async () => {
    const structure = await loadStructure(file);
    expect(chainsFromIndex(structure, buildResidueIndex(structure))).toEqual(
      EXPECTED,
    );
  });

  it("labels chains by auth_asym_id, not label_asym_id", async () => {
    // The mmCIF labels the three polymers A/B/C and the ligand and waters
    // D/E/F, while the author calls the polymers H/L/M. Reading the label
    // would rename every chain and invent three the backend never reports.
    const structure = await loadStructure(file);
    const index = buildResidueIndex(structure);
    expect([...index.chainCounts.keys()].sort()).toEqual(["H", "L", "M"]);
  });

  it("excludes HETATM residues — the MSE inside chain H included", async () => {
    const structure = await loadStructure(file);
    const records = extractResidueRecords(structure);
    const names = records.map((r) => residueName(structure, r.residue));
    expect(names).not.toContain("MSE");
    expect(names).not.toContain("HEM");
    expect(names).not.toContain("HOH");
    expect(records).toHaveLength(14);
  });

  it("does not derive the ordinal from auth_seq_id", async () => {
    // Chain H is written 27, 28, [MSE 29 skipped], 34, 34A, 35, so its five
    // ordinals map to author residues 27, 28, 34, 34A, 35 — every one of them
    // a different number from its ordinal.
    const structure = await loadStructure(file);
    const index = buildResidueIndex(structure);
    expect(index.chainCounts.get("H")).toBe(5);

    const records = extractResidueRecords(structure);
    const authOf = new Map(records.map((r) => [r.residue, r.authSeqId]));
    const authSeqIds = [1, 2, 3, 4, 5].map((n) =>
      authOf.get(index.keyToResidue.get(`H:${n}`)!),
    );
    expect(authSeqIds).toEqual([27, 28, 34, 34, 35]);
    // H:3 and H:4 share an auth_seq_id (insertion code) — proof the ordinal is
    // a different quantity, and that both survive as distinct residues.
    expect(index.keyToResidue.get("H:3")).not.toBe(index.keyToResidue.get("H:4"));
  });

  it("agrees with the residue counts the API reports, so no drift is logged", async () => {
    const structure = await loadStructure(file);
    const apiChains = [
      { label: "H", residue_count: 5 },
      { label: "L", residue_count: 4 },
      { label: "M", residue_count: 5 },
    ];
    expect(findIndexDrift(buildResidueIndex(structure), apiChains)).toEqual([]);
  });

  it("round-trips every key through a loci and back", async () => {
    // This is the bidirectional sync itself: panel -> 3D via keysToLoci, and
    // 3D -> panel via resolveResidueLocus. A key that comes back as a
    // different key is a click landing on the wrong residue.
    const structure = await loadStructure(file);
    const index = buildResidueIndex(structure);

    for (const key of index.keyToResidue.keys()) {
      const loci = keysToLoci(structure, [key], index);
      expect(StructureElement.Loci.isEmpty(loci)).toBe(false);
      expect(resolveResidueLocus(loci, index)).toEqual({ kind: "residue", key });
    }
  });
});

describe("residue index across formats", () => {
  it("builds the identical ordinal map from the PDB and the mmCIF", async () => {
    // The seam, stated directly: one structure, two formats, one numbering.
    // If this fails, every residue click on an RCSB import is off by however
    // much the two parsers disagree.
    const [pdb, cif] = await Promise.all([
      loadStructure("parity_multichain.pdb"),
      loadStructure("parity_multichain.cif"),
    ]);

    const fromPdb = chainsFromIndex(pdb, buildResidueIndex(pdb));
    const fromCif = chainsFromIndex(cif, buildResidueIndex(cif));

    expect(fromCif).toEqual(fromPdb);
    expect(fromCif).toEqual(EXPECTED);
  });
});
