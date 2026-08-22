import { describe, it, expect } from "vitest";

import {
  chebiUrl,
  ecUrl,
  formatRange,
  goUrl,
  omimUrl,
  rheaUrl,
  taxonomyUrl,
  uniprotUrl,
} from "@/lib/annotation-links";

describe("annotation links", () => {
  it("links a GO term to QuickGO", () => {
    expect(goUrl("GO:0005615")).toBe("https://www.ebi.ac.uk/QuickGO/term/GO:0005615");
  });

  it("strips the RHEA prefix, which the Rhea URL does not carry", () => {
    expect(rheaUrl("RHEA:10596")).toBe("https://www.rhea-db.org/rhea/10596");
  });

  it("keeps the CHEBI prefix, which the ChEBI URL does carry", () => {
    expect(chebiUrl("CHEBI:30616")).toBe(
      "https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:30616",
    );
  });

  it("links complete and partial EC numbers", () => {
    expect(ecUrl("2.7.10.1")).toBe("https://enzyme.expasy.org/EC/2.7.10.1");
    expect(ecUrl("2.7.10.-")).toBe("https://enzyme.expasy.org/EC/2.7.10.-");
  });

  it("links OMIM, taxonomy and the UniProt entry itself", () => {
    expect(omimUrl("125852")).toBe("https://www.omim.org/entry/125852");
    expect(taxonomyUrl(9606)).toBe("https://www.uniprot.org/taxonomy/9606");
    expect(uniprotUrl("P01308")).toBe("https://www.uniprot.org/uniprotkb/P01308");
  });

  it("returns null rather than a dead link for malformed identifiers", () => {
    // A dead link is worse than no link: it looks like data and isn't.
    expect(goUrl("0005615")).toBeNull();
    expect(goUrl("GO:12")).toBeNull();
    expect(rheaUrl("10596")).toBeNull();
    expect(chebiUrl("30616")).toBeNull();
    expect(ecUrl("kinase")).toBeNull();
    expect(omimUrl("MIM-125852")).toBeNull();
    expect(uniprotUrl("nope")).toBeNull();
    expect(taxonomyUrl(0)).toBeNull();
  });

  it("formats residue ranges the way UniProt writes them", () => {
    expect(formatRange(646, 668)).toBe("646–668");
    // A point feature (a modified residue) is one position, not "1068–1068".
    expect(formatRange(1068, 1068)).toBe("1068");
    expect(formatRange(null, null)).toBe("");
    expect(formatRange(24, null)).toBe("24");
  });
});
