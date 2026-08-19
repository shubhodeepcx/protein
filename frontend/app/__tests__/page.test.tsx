import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import HomePage from "@/app/page";

/**
 * The landing page kept denying features that had already shipped — a "P2"
 * badge, an Upload button disabled since before upload existed, and panel copy
 * promising the sequence and analytics work "arrives in P4" / "arrive in P3".
 * These assertions are deliberately about *claims*, not layout.
 */
describe("landing page", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ status: "ok" }),
      }),
    );
    render(<HomePage />);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  const PHASE_PROMISE = /arrives? in P\d|coming in P\d|in flight/i;

  it("does not describe any shipped phase as still to come", () => {
    expect(document.body.textContent ?? "").not.toMatch(PHASE_PROMISE);
  });

  it("says nothing of the sort on the Sequence or Analytics tabs either", () => {
    // Only the active tab's content is mounted, so the copy that promised
    // "arrives in P4" is invisible to a single-render assertion. Visit each.
    for (const name of [/sequence/i, /analytics/i, /overview/i]) {
      fireEvent.click(screen.getByRole("tab", { name }));
      expect(document.body.textContent ?? "").not.toMatch(PHASE_PROMISE);
    }
  });

  it("does not badge the app with a superseded phase number", () => {
    expect(screen.queryByText(/^P[0-5]$/)).toBeNull();
  });

  it("offers a working Upload control", () => {
    // Upload shipped in P2; the header control stayed `disabled` regardless.
    const upload = screen.getByRole("link", { name: /upload/i });
    expect(upload).toHaveAttribute("href", "#upload");
    // Nothing named "upload" anywhere on the page is disabled — the DropZone
    // itself also exposes an upload control.
    const disabled = screen
      .queryAllByRole("button", { name: /upload/i })
      .filter((el) => el.hasAttribute("disabled"));
    expect(disabled).toEqual([]);
  });

  it("anchors that Upload control at the drop zone", () => {
    expect(document.querySelector("#upload")).not.toBeNull();
  });
});
