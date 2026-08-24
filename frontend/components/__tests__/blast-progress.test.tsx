import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import { BlastProgress } from "@/components/blast-progress";
import type { BlastJobStatus } from "@/lib/types";

const JOB_ID = "ncbiblast-R20191128-094014-0332-71107816-p1m";

function job(patch: Partial<BlastJobStatus> = {}): BlastJobStatus {
  return {
    job_id: JOB_ID,
    status: "RUNNING",
    finished: false,
    program: "blastp",
    database: "uniprotkb",
    query_length: 605,
    query_source: "1CRN chain A",
    submitted_at: "2026-08-23T10:00:00Z",
    elapsed_seconds: 154,
    poll_count: 12,
    message: "Running at EBI. Protein searches usually take 30 s to a few minutes.",
    result: null,
    ...patch,
  };
}

describe("BlastProgress", () => {
  afterEach(cleanup);

  it("shows how long the search has really been running", () => {
    // The requirement this component exists for: a multi-minute wait must not
    // look hung. Elapsed time is what distinguishes "slow" from "dead".
    render(<BlastProgress job={job({ elapsed_seconds: 154 })} />);

    expect(screen.getByText("2m 34s")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("relays the server's own explanation of the status", () => {
    render(<BlastProgress job={job()} />);

    expect(
      screen.getByText(/Protein searches usually take 30 s to a few minutes/),
    ).toBeInTheDocument();
  });

  it("announces status changes to assistive technology", () => {
    render(<BlastProgress job={job()} />);

    const region = screen.getByTestId("blast-progress");
    expect(region).toHaveAttribute("role", "status");
    expect(region).toHaveAttribute("aria-live", "polite");
  });

  it("shows the job id, program, database and query so the run is identifiable", () => {
    render(<BlastProgress job={job()} />);

    expect(screen.getByText(JOB_ID)).toBeInTheDocument();
    expect(screen.getByText("blastp")).toBeInTheDocument();
    expect(screen.getByText("uniprotkb")).toBeInTheDocument();
    expect(screen.getByText("1CRN chain A · 605 aa")).toBeInTheDocument();
  });

  it("drops the elapsed timer once the job is finished", () => {
    // A ticking clock on a completed search reads as "still working".
    render(<BlastProgress job={job({ status: "FINISHED", finished: true })} />);

    expect(screen.getByText("Search complete")).toBeInTheDocument();
    expect(screen.queryByText("2m 34s")).not.toBeInTheDocument();
  });

  it("distinguishes a failed search from an expired job", () => {
    // Different user actions: one means fix the query, the other means re-run.
    const { unmount } = render(
      <BlastProgress job={job({ status: "FAILURE", finished: true })} />,
    );
    expect(screen.getByText("Search failed")).toBeInTheDocument();
    unmount();

    render(<BlastProgress job={job({ status: "NOT_FOUND", finished: true })} />);
    expect(screen.getByText("Job expired")).toBeInTheDocument();
  });

  it("labels a queued job as queued rather than running", () => {
    render(<BlastProgress job={job({ status: "QUEUED" })} />);
    expect(screen.getByText("Queued")).toBeInTheDocument();
  });
});
