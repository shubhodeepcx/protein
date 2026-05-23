import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

// Mock next/navigation so DropZone can be mounted without a Next.js runtime.
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

import { DropZone } from "@/components/drop-zone";

function getZone(): HTMLElement {
  return screen.getByTestId("drop-zone");
}

describe("DropZone", () => {
  beforeEach(() => {
    cleanup();
    pushMock.mockReset();
  });

  it("renders the idle prompt with browse affordance", () => {
    render(<DropZone />);
    expect(screen.getByText(/Drop a/i)).toBeInTheDocument();
    expect(screen.getByText(/click to browse/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /upload protein structure/i }),
    ).toBeInTheDocument();
  });

  it("flips the dragging state on dragover and resets on dragleave", () => {
    render(<DropZone />);
    const zone = getZone();
    expect(zone.dataset.dragging).toBe("false");

    fireEvent.dragOver(zone);
    expect(zone.dataset.dragging).toBe("true");
    expect(zone.className).toContain("border-primary");

    fireEvent.dragLeave(zone);
    expect(zone.dataset.dragging).toBe("false");
    expect(zone.className).not.toContain("border-primary");
  });

  it("rejects an unsupported extension with an inline error and never calls the router", () => {
    render(<DropZone />);
    const input = screen.getByTestId("drop-zone-input") as HTMLInputElement;
    const badFile = new File(["junk"], "notes.txt", { type: "text/plain" });

    fireEvent.change(input, { target: { files: [badFile] } });

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/Unsupported extension/i);
    expect(alert.textContent).toMatch(/\.pdb/);
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("rejects an oversized file with a max-size message", () => {
    render(<DropZone />);
    const input = screen.getByTestId("drop-zone-input") as HTMLInputElement;
    // 51 MB sentinel (> 50 MB cap).
    const big = new File(["x"], "huge.pdb", { type: "chemical/x-pdb" });
    Object.defineProperty(big, "size", { value: 51 * 1024 * 1024 });

    fireEvent.change(input, { target: { files: [big] } });

    expect(screen.getByRole("alert").textContent).toMatch(
      /too large|Max 50 MB/i,
    );
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("rejects an empty file", () => {
    render(<DropZone />);
    const input = screen.getByTestId("drop-zone-input") as HTMLInputElement;
    const empty = new File([], "empty.pdb", { type: "chemical/x-pdb" });

    fireEvent.change(input, { target: { files: [empty] } });

    expect(screen.getByRole("alert").textContent).toMatch(/empty/i);
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("keeps the dragging state cleared after a drop event", () => {
    render(<DropZone />);
    const zone = getZone();

    fireEvent.dragOver(zone);
    expect(zone.dataset.dragging).toBe("true");

    // Drop with no files: should clear dragging and not call the router.
    fireEvent.drop(zone, { dataTransfer: { files: [] } });
    expect(zone.dataset.dragging).toBe("false");
    expect(pushMock).not.toHaveBeenCalled();
  });
});
