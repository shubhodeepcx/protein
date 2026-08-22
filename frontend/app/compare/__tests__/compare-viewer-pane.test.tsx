import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import type { CompareProteinRef } from "@/lib/types";

/**
 * What one comparison pane pushes into its Mol* viewer.
 *
 * The viewer component itself is mocked: this is about the wiring, not about
 * WebGL. The wiring that matters is `has_plddt`, which is per-pane. On
 * `/compare` the two panes routinely disagree about it — that is exactly the
 * predicted-vs-experimental pair A3 is built around — so a pane that passed a
 * constant, or read the other pane's flag, would render an AlphaFold model's
 * confidence scale backwards while looking entirely normal.
 */

const loadStructure = vi.fn(async () => {});
const setRepresentation = vi.fn();
const setColoring = vi.fn();
let onReadyCallback: (() => void) | null = null;

vi.mock("@/components/molstar-viewer", () => ({
  default: React.forwardRef(function MockViewer(
    { onReady }: { onReady?: () => void },
    ref: React.Ref<unknown>,
  ) {
    onReadyCallback = onReady ?? null;
    React.useImperativeHandle(ref, () => ({
      loadStructure,
      setRepresentation,
      setColoring,
      highlightResidues: vi.fn(),
      resetCamera: vi.fn(),
    }));
    return <div data-testid="mock-molstar" />;
  }),
}));

// `next/dynamic` would defer the mocked module behind its own loading state;
// resolving it eagerly keeps the test about the pane's effects.
/** A component that accepts arbitrary props plus a ref — what the mock forwards to. */
type RefForwardingComponent = React.ComponentType<
  Record<string, unknown> & { ref?: React.Ref<unknown> }
>;

vi.mock("next/dynamic", () => ({
  default: (loader: () => Promise<{ default: RefForwardingComponent }>) => {
    let Loaded: RefForwardingComponent | null = null;
    void loader().then((mod) => {
      Loaded = mod.default;
    });
    return React.forwardRef(function Dynamic(
      props: Record<string, unknown>,
      ref: React.Ref<unknown>,
    ) {
      const [, force] = React.useState(0);
      React.useEffect(() => {
        if (!Loaded) void loader().then(() => force((n) => n + 1));
      }, []);
      if (!Loaded) return null;
      const Component: RefForwardingComponent = Loaded;
      return <Component {...props} ref={ref} />;
    });
  },
}));

function protein(overrides: Partial<CompareProteinRef> = {}): CompareProteinRef {
  return {
    id: "aaa111",
    source: "rcsb",
    source_id: "1CRN",
    name: "Crambin",
    organism: "Crambe hispanica",
    file_url: "/api/proteins/aaa111/file",
    file_format: "mmcif",
    has_plddt: false,
    ...overrides,
  };
}

async function renderPane(p: CompareProteinRef, side = "A") {
  const { CompareViewerPane } = await import("../compare-viewer-pane");
  const view = render(
    <CompareViewerPane
      protein={p}
      side={side}
      representation="cartoon"
      coloring="plddt"
    />,
  );
  await waitFor(() => expect(screen.getByTestId("mock-molstar")).toBeInTheDocument());
  // The pane loads only once the viewer reports ready, as the viewer page does.
  await React.act(async () => {
    onReadyCallback?.();
  });
  return view;
}

beforeEach(() => {
  loadStructure.mockClear();
  setRepresentation.mockClear();
  setColoring.mockClear();
  onReadyCallback = null;
});

afterEach(cleanup);

describe("CompareViewerPane", () => {
  it("loads its own structure at the absolute API url, in its own format", async () => {
    await renderPane(protein());
    await waitFor(() => expect(loadStructure).toHaveBeenCalled());
    const [url, format] = loadStructure.mock.calls[0] as unknown as [string, string];
    expect(url).toMatch(/\/api\/proteins\/aaa111\/file$/);
    expect(url.startsWith("http")).toBe(true);
    expect(format).toBe("mmcif");
  });

  it("passes its own protein's has_plddt when colouring — false side", async () => {
    await renderPane(protein({ has_plddt: false }));
    await waitFor(() => expect(setColoring).toHaveBeenCalled());
    expect(setColoring).toHaveBeenLastCalledWith("plddt", { hasPlddt: false });
  });

  it("passes its own protein's has_plddt when colouring — true side", async () => {
    // The same pane component, the other structure. A hard-coded flag passes
    // one of these two tests and fails the other.
    await renderPane(
      protein({ id: "bbb222", source: "alphafold", has_plddt: true, file_format: "pdb" }),
      "B",
    );
    await waitFor(() => expect(setColoring).toHaveBeenCalled());
    expect(setColoring).toHaveBeenLastCalledWith("plddt", { hasPlddt: true });
  });

  it("applies the shared representation", async () => {
    await renderPane(protein());
    await waitFor(() => expect(setRepresentation).toHaveBeenCalledWith("cartoon"));
  });

  it("labels the pane with its side and source", async () => {
    await renderPane(protein({ has_plddt: true, source: "alphafold" }), "B");
    const pane = screen.getByTestId("compare-pane-B");
    expect(pane).toHaveTextContent("B");
    expect(pane).toHaveTextContent("alphafold");
    expect(pane).toHaveTextContent("Crambin");
  });
});
