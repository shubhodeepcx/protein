import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import HomePage from "@/app/page";
import { ViewerRail } from "@/components/viewer-rail";
import { DATA_SOURCES, RAIL_TABS } from "@/components/rail-tab-preview";
import { useStore } from "@/lib/store";

/**
 * The landing page describes the workspace a visitor has not opened yet, so
 * its copy is the one thing in the app with nothing to keep it honest. It has
 * drifted twice: it promised a chain tree that did not exist, and it went on
 * advertising three rail tabs for two phases after the rail grew to five.
 *
 * These tests compare the promise against the thing promised.
 */

function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ status: "ok" }),
    }),
  );
}

describe("landing page rail preview", () => {
  beforeEach(stubFetch);

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("previews exactly the tabs the viewer's rail renders", () => {
    useStore.setState({
      current: {
        id: "x",
        source: "uploaded",
        source_id: null,
        name: "Test",
        organism: null,
        file_url: "/api/proteins/x/file",
        file_format: "pdb",
        chains: [],
        residue_count: 0,
        atom_count: 0,
        molecular_weight: 0,
        has_plddt: false,
        warnings: [],
      },
      analytics: null,
    });
    render(<ViewerRail proteinId="x" />);
    const real = screen
      .getAllByRole("tab")
      .map((el) => (el.textContent ?? "").trim());
    cleanup();

    render(<HomePage />);
    const promised = screen
      .getAllByRole("tab")
      .map((el) => (el.textContent ?? "").trim());

    expect(promised).toEqual(real);
    // Guards the assertion itself: if both ever render zero tabs the equality
    // above would pass vacuously.
    expect(real.length).toBeGreaterThanOrEqual(5);
  });

  it("names a real data source for every previewed tab", () => {
    for (const tab of RAIL_TABS) {
      expect(tab.source.trim().length).toBeGreaterThan(0);
      expect(tab.items.length).toBeGreaterThan(0);
    }
  });

  it("no longer badges the left rail as empty", () => {
    render(<HomePage />);
    expect(screen.queryByText(/^empty$/i)).toBeNull();
  });

  it("offers the demo, the databases and the drop zone as real routes", () => {
    render(<HomePage />);
    // Scoped to the rail's own nav on purpose. Querying the whole document
    // proved nothing: the header carries its own links to `#upload` and the
    // viewer strip to `/viewer/demo`, so a broken rail href was still
    // "found" somewhere else on the page.
    const nav = screen.getByTestId("quick-actions");
    const hrefs = Array.from(nav.querySelectorAll("a")).map((a) =>
      a.getAttribute("href"),
    );
    expect(hrefs).toEqual(["/viewer/demo", "/search", "#upload"]);
  });

  it("lists a database the backend really talks to, for each source card", () => {
    // The landing page's other failure mode is claiming an integration that
    // does not exist. Every host advertised here has to appear in a client
    // under `backend/app/services/`, so the claim is falsifiable from the
    // repository rather than taken on trust.
    const servicesDir = join(process.cwd(), "..", "backend", "app", "services");
    const sources = readdirSync(servicesDir)
      .filter((f) => f.endsWith(".py"))
      .map((f) => readFileSync(join(servicesDir, f), "utf8"))
      .join("\n");

    expect(DATA_SOURCES.length).toBeGreaterThan(0);
    for (const source of DATA_SOURCES) {
      expect(sources, `${source.name} (${source.host})`).toContain(source.host);
    }
  });

  it("renders every source card on the page", () => {
    render(<HomePage />);
    for (const source of DATA_SOURCES) {
      expect(screen.getByText(source.name)).toBeInTheDocument();
    }
  });

  it("describes the chain tree as what the rail becomes, not as a thing to come", () => {
    render(<HomePage />);
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/chain tree/i);
    // The old copy — "Load a protein to explore its chains ... side by side"
    // — promised a rail that had never been built. The rail exists now.
    expect(text).not.toMatch(/will (?:be )?(?:soon|arrive)|not yet built/i);
  });
});
