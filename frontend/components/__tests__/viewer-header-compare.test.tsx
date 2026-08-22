import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import { ViewerHeader } from "@/components/viewer-header";

/**
 * The way into `/compare` from a protein you are already looking at.
 *
 * Without an entry point the comparison view is reachable only by hand-building
 * a URL, which is the difference between a shipped feature and a route that
 * exists.
 */
describe("ViewerHeader — compare affordance", () => {
  afterEach(cleanup);

  it("links to /compare with this protein already on side A", () => {
    render(
      <ViewerHeader
        title="Crambin"
        source="rcsb"
        proteinId="abc123"
        onResetCamera={() => {}}
      />,
    );
    const link = screen.getByRole("link", { name: /Compare/ });
    expect(link).toHaveAttribute("href", "/compare?a=abc123");
  });

  it("percent-encodes the id it puts in the query string", () => {
    render(
      <ViewerHeader
        title="Crambin"
        source="rcsb"
        proteinId="a b&c"
        onResetCamera={() => {}}
      />,
    );
    expect(screen.getByRole("link", { name: /Compare/ })).toHaveAttribute(
      "href",
      "/compare?a=a%20b%26c",
    );
  });

  it("offers nothing to compare before the protein has loaded", () => {
    // The viewer page passes `proteinId` only once the summary is in hand; a
    // link built from an undefined id would 404 the comparison instead.
    render(<ViewerHeader title="Loading" source={null} onResetCamera={() => {}} />);
    expect(screen.queryByRole("link", { name: /Compare/ })).toBeNull();
  });
});
