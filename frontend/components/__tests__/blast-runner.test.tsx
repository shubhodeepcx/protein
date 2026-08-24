import React from "react";
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup, act, fireEvent, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { BlastRunner } from "@/components/blast-runner";
import { useStore } from "@/lib/store";
import type { BlastJobStatus, ChainInfo } from "@/lib/types";

const PROTEIN = "abc123";
const JOB_ID = "ncbiblast-R20191128-094014-0332-71107816-p1m";

const CHAINS: ChainInfo[] = [
  { id: "a", label: "A", sequence: "MALRKGG", residue_count: 605 },
  { id: "b", label: "B", sequence: "MKWV", residue_count: 30 },
];

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
    elapsed_seconds: 12,
    poll_count: 3,
    message: "Running at EBI.",
    result: null,
    ...patch,
  };
}

const submitSpy = vi.fn();
const resumeSpy = vi.fn();
const clearSpy = vi.fn();

function setStore(patch: Record<string, unknown> = {}) {
  act(() => {
    useStore.setState({
      blastJob: null,
      blastProteinId: null,
      blastSubmitting: false,
      blastError: null,
      submitBlast: async (...args: unknown[]) => {
        submitSpy(...args);
      },
      resumeBlast: async (...args: unknown[]) => {
        resumeSpy(...args);
      },
      clearBlast: (...args: unknown[]) => {
        clearSpy(...args);
      },
      ...patch,
    } as never);
  });
}

describe("BlastRunner", () => {
  beforeEach(() => {
    submitSpy.mockReset();
    resumeSpy.mockReset();
    clearSpy.mockReset();
    window.localStorage.clear();
    setStore();
  });
  afterEach(cleanup);

  it("shows the form and no progress until a search is started", () => {
    render(<BlastRunner proteinId={PROTEIN} chains={CHAINS} />);

    expect(screen.getByRole("button", { name: /Run blastp at EBI/ })).toBeInTheDocument();
    expect(screen.queryByTestId("blast-progress")).toBeNull();
  });

  it("submits blastp against the chosen database and threshold", () => {
    render(<BlastRunner proteinId={PROTEIN} chains={CHAINS} />);

    fireEvent.change(screen.getByLabelText("Database"), {
      target: { value: "uniprotkb_swissprot" },
    });
    fireEvent.change(screen.getByLabelText("E-value"), { target: { value: "1e-10" } });
    fireEvent.click(screen.getByRole("button", { name: /Run blastp at EBI/ }));

    expect(submitSpy).toHaveBeenCalledWith(PROTEIN, {
      protein_id: PROTEIN,
      chain_id: undefined,
      program: "blastp",
      database: "uniprotkb_swissprot",
      exp: "1e-10",
    });
  });

  it("lets a multi-chain structure pick the chain to search with", () => {
    render(<BlastRunner proteinId={PROTEIN} chains={CHAINS} />);

    fireEvent.change(screen.getByLabelText("Chain"), { target: { value: "B" } });
    fireEvent.click(screen.getByRole("button", { name: /Run blastp at EBI/ }));

    expect(submitSpy.mock.calls[0][1]).toMatchObject({ chain_id: "B" });
  });

  it("hides the chain picker for a single-chain structure", () => {
    render(<BlastRunner proteinId={PROTEIN} chains={[CHAINS[0]]} />);
    expect(screen.queryByLabelText("Chain")).toBeNull();
  });

  it("resumes a remembered job on mount instead of starting a second one", () => {
    // The "survives navigating away and back" requirement. Submitting again
    // would queue a duplicate search at EBI for no reason.
    window.localStorage.setItem(`proteolens.blast.${PROTEIN}`, JOB_ID);

    render(<BlastRunner proteinId={PROTEIN} chains={CHAINS} />);

    expect(resumeSpy).toHaveBeenCalledWith(PROTEIN, JOB_ID);
    expect(submitSpy).not.toHaveBeenCalled();
  });

  it("does not resume anything when no job was remembered", () => {
    render(<BlastRunner proteinId={PROTEIN} chains={CHAINS} />);
    expect(resumeSpy).not.toHaveBeenCalled();
  });

  it("replaces the form with live progress while a search runs", () => {
    setStore({ blastJob: job(), blastProteinId: PROTEIN });
    render(<BlastRunner proteinId={PROTEIN} chains={CHAINS} />);

    expect(screen.getByTestId("blast-progress")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Run blastp at EBI/ })).toBeNull();
  });

  it("never shows a job that belongs to a different protein", () => {
    setStore({ blastJob: job(), blastProteinId: "some-other-protein" });
    render(<BlastRunner proteinId={PROTEIN} chains={CHAINS} />);

    expect(screen.queryByTestId("blast-progress")).toBeNull();
    expect(screen.getByRole("button", { name: /Run blastp at EBI/ })).toBeInTheDocument();
  });

  it("renders the hits once the job finishes", () => {
    setStore({
      blastProteinId: PROTEIN,
      blastJob: job({
        status: "FINISHED",
        finished: true,
        result: {
          program: "blastp",
          version: null,
          databases: ["uniprotkb_swissprot"],
          query_id: "ALS_HUMAN",
          query_definition: null,
          query_length: 605,
          hit_count: 1,
          hits: [
            {
              rank: 1,
              accession: "P35858",
              entry_id: "ALS_HUMAN",
              description: "Acid labile subunit",
              database: "SP",
              organism: "Homo sapiens",
              gene: "IGFALS",
              length: 605,
              url: null,
              uniprot_accession: "P35858",
              identity_percent: 100,
              expect: 0,
              score: 3142,
              bit_score: 1214.91,
              align_length: 605,
              gaps: 0,
              hsps: [],
            },
          ],
          started_at: null,
          finished_at: null,
        },
      }),
    });
    render(<BlastRunner proteinId={PROTEIN} chains={CHAINS} />);

    expect(screen.getByTestId("blast-hit-P35858")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /New search/ })).toBeInTheDocument();
  });

  it("offers a new search only once the current one is finished", () => {
    setStore({ blastJob: job(), blastProteinId: PROTEIN });
    render(<BlastRunner proteinId={PROTEIN} chains={CHAINS} />);

    expect(screen.queryByRole("button", { name: /New search/ })).toBeNull();
  });

  it("clears the job for this protein when a new search is requested", async () => {
    setStore({
      blastJob: job({ status: "FINISHED", finished: true }),
      blastProteinId: PROTEIN,
    });
    render(<BlastRunner proteinId={PROTEIN} chains={CHAINS} />);

    fireEvent.click(screen.getByRole("button", { name: /New search/ }));

    await waitFor(() => expect(clearSpy).toHaveBeenCalledWith(PROTEIN));
  });

  it("surfaces a submit failure to the user", () => {
    setStore({ blastError: { status: 502, message: "Could not reach EBI" } });
    render(<BlastRunner proteinId={PROTEIN} chains={CHAINS} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Could not reach EBI");
  });
});
