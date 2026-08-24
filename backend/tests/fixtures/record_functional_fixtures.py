"""Records the A5 fixtures from the live services. Run offline; output committed.

    cd backend && python tests/fixtures/record_functional_fixtures.py

AGENTS.md forbids tests that reach a live API, and this project's decisions log
(2026-08-23) forbids hand-authoring an upstream payload — a hand-written fixture
can only ever encode what the author already believed. So the four files below
are *recordings*, and this script is the provenance record for them.

What is recorded, and why each one is here:

* ``uniprot_functional_P00698.json`` — hen egg-white lysozyme. The load-bearing
  fixture: UniProt numbers its 18-residue signal peptide, every lysozyme crystal
  structure numbers the mature chain from 1, and the answer is famous. Active
  sites at UniProt 53 and 70 must land on Glu35 and Asp52 of the structure; the
  substrate-binding site at 119 must land on Asp101. An off-by-any mapping bug
  moves them somewhere that still looks plausible in 3D, which is exactly the
  failure this feature has to be proof against.
* ``1HEW.pdb`` — that structure, with tri-N-acetylchitotriose bound in the
  cleft. The only fixture in the repo that carries a real non-water ligand, so
  it is the only one that can prove the observed-contact half end to end.
* ``uniprot_functional_P00533.json`` — EGFR. An entry whose binding site is a
  *range* (718-726, the ATP phosphate-binding loop) rather than a single
  residue, plus an active site and an "other site". AlphaFold models this
  accession over its full length, so it is also the no-offset case.
* ``uniprot_functional_P04585.json`` — HIV-1 Gag-Pol. The only one of the four
  carrying a ``DNA binding`` feature and metal (Mg2+) binding sites, and the
  extreme offset case: the protease active site is residue 25 of the mature
  enzyme and residue 513 of the polyprotein UniProt indexes.

Note for the field list: UniProt no longer serves ``ft_metal``, ``ft_np_bind``
or ``ft_ca_bind`` — all three are now 400 "Invalid fields parameter value", and
metal/nucleotide binding is folded into ``ft_binding`` with a ``ligand`` object.
Checked live on 2026-08-24; the four names below are the ones that answer 200.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

FIXTURES = Path(__file__).resolve().parent

UNIPROT_ENTRY = "https://rest.uniprot.org/uniprotkb/{accession}.json"
RCSB_FILE = "https://files.rcsb.org/download/{entry}.pdb"

# Mirrors `UniProtClient.FUNCTIONAL_FIELDS`; kept in one place there and echoed
# here so a recording is always made with the field set production asks for.
FIELDS = (
    "accession,id,protein_name,sequence,ft_act_site,ft_binding,ft_site,ft_dna_bind"
)

ACCESSIONS = ("P00698", "P00533", "P04585")
STRUCTURES = ("1HEW",)


def record_uniprot(accession: str) -> None:
    response = httpx.get(
        UNIPROT_ENTRY.format(accession=accession),
        params={"fields": FIELDS},
        timeout=30.0,
    )
    response.raise_for_status()
    target = FIXTURES / f"uniprot_functional_{accession}.json"
    target.write_text(
        json.dumps(response.json(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {target.name} ({target.stat().st_size} bytes)")


def record_structure(entry: str) -> None:
    response = httpx.get(RCSB_FILE.format(entry=entry), timeout=60.0)
    response.raise_for_status()
    target = FIXTURES / f"{entry}.pdb"
    # Verbatim, including waters: trimming it would make the fixture something
    # this repo derived rather than something RCSB published.
    target.write_bytes(response.content)
    print(f"wrote {target.name} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    for accession in ACCESSIONS:
        record_uniprot(accession)
    for entry in STRUCTURES:
        record_structure(entry)
