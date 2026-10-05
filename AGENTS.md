# AGENTS.md — Rules for AI contributors working on this repo

This file is picked up automatically by AI coding agents. Every agent — and every parallel sub-agent — must read this **before** making any change.

If you are a human, the same rules apply; the tracker discipline is the load-bearing piece.

---

## 0. Mandatory reading order

Read these files end-to-end before your first edit. Do not skim.

1. [docs/spec.md](docs/spec.md) — product + technical spec for the full 6-month platform.
2. [docs/sdlc.md](docs/sdlc.md) — phase plan and sprint structure.
3. [docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md](docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md) — the **active** design for the current slice.
4. [docs/PROJECT_TRACKER.md](docs/PROJECT_TRACKER.md) — what's done, in flight, and ready to claim.
5. This file.
6. Any `AGENTS.md` deeper in the tree (e.g. `frontend/AGENTS.md`, `backend/AGENTS.md`) if present — they refine the rules for that area.

If you start work without reading the tracker, you will collide with another agent. Do not skip step 4.

---

## 1. Claim-before-code

**Before** the first `Edit`, `Write`, or `Bash` that mutates the repo:

1. Open `docs/PROJECT_TRACKER.md`.
2. Pick a task from **Ready to claim** that has no unresolved dependencies.
3. Move that task into **In progress** with:
   - **Owner** — the owner's handle (`shubhodeep`).
   - **Branch** — `feature/<phase>-<short-slug>` (e.g. `feature/p2-upload-parser`).
   - **Status** — `wip`.
   - **Notes** — anything the next agent needs to know.
4. Commit the tracker update on the new branch as your first commit. This is the public claim.

If two agents claim the same task in the same window, the one with the earlier commit timestamp wins; the other reverts the claim and picks something else.

---

## 2. Branch and commit conventions

- **Branch name:** `feature/<phase>-<short-slug>`. Examples: `feature/p0-frontend-init`, `feature/p3-analytics`.
- **Base branch:** `main`. Rebase, do not merge `main` into your feature branch.
- **Commits:** small, focused, present-tense subject under 70 chars. Reference the tracker task in the body when useful.
- **Author:** all commits are authored by Shubhodeep Chatterjee.
- **No co-author footers.** Do not add `Co-Authored-By` lines for any AI agent or tool.

- **Never** pass `--no-verify`, `--no-gpg-sign`, or `-c commit.gpgsign=false`. If a hook fails, fix the underlying issue and create a new commit. Do not amend through a hook failure.
- **Never** force-push to `main`. Force-push to your own feature branch only when you have a real reason (e.g. squashing pre-merge).

---

## 3. Coding standards

### Frontend (`frontend/`)
- TypeScript `strict: true`. No `any` in shipped code; `unknown` + narrowing is fine.
- App Router (Next.js 14+). Server components by default; `"use client"` only when needed (Mol*, Zustand, drag-and-drop).
- Components ≤ 200 LOC. Split when they grow.
- shadcn/ui primitives over hand-rolled UI.
- Tailwind utilities; no styled-components, no CSS-in-JS.
- State in Zustand slices under `lib/store/`.

### Backend (`backend/`)
- Python 3.11+. Full type hints on every function signature.
- Pydantic models at the API boundary; never return a raw dict.
- Pure functions in `services/analytics.py` and friends — no I/O inside analytics.
- HTTP clients use `httpx.AsyncClient` with explicit timeouts (10s for external).
- Logging via `logging.getLogger(__name__)`, never `print`.

### Tests
- Backend: `pytest`, fixtures in `backend/tests/fixtures/`. Recorded HTTP for external clients via `respx` or `pytest-httpx`. Never hit a live API from CI.
- Frontend: `vitest` for unit, `@testing-library/react` for component. Mol* itself is a trusted library — do not unit-test it.
- A new module without a test is not done.

---

## 4. Definition of done

A task is **done** only when **all** of the following hold:

1. The code merges cleanly to `main`.
2. The phase smoke test from `docs/smoke-tests.md` passes (run it yourself; do not claim done on type-check alone).
3. `PROJECT_TRACKER.md` is updated:
   - Task moved from **In progress** to **Done** with merge date and PR/commit link.
   - Any new dependent tasks added to **Ready to claim**.
4. If an architectural choice was made, append a row to the **Decisions log**.

If you discover a follow-up task while working, add it to **Ready to claim** with a note — do not silently expand your own scope.

---

## 5. Parallel work etiquette

The owner's #1 behavioural rule is **parallel sub-agents for independent work** — use it.

- **Independent tasks** — different phases, or same phase but non-overlapping files — are safe to run in parallel, each in its own git worktree. Each parallel agent gets its own tracker claim and its own branch.
- **Cross-phase or shared-file work** — serialize. Finish one, merge, then start the next.
- **Task split:**
  - **Reasoning-heavy work** — planning, deep codebase scanning, reasoning-heavy refactors, coding decisions, anything where judgment matters — goes to the strongest reasoning sub-agent available.
  - **Mechanical work** — write-out, audits, applying explicit review feedback verbatim, dedup / extraction passes.
- **After fixes** — run an independent audit pass before merging.
- A parallel sub-agent **does not** update the tracker on its own — the orchestrating agent records the result. This prevents merge conflicts on the tracker file.

---

## 6. Destructive-action gate

Mirrors the user's #1 hard global rule. **Before** executing any action that mutates persistent or shared state, stop and ask the user in-message. Wait for explicit "yes run it" for that specific action.

**Covered actions** (non-exhaustive):
- `git reset --hard`, `git push --force` (always disallowed to `main`), `git branch -D`, `git rebase` on shared branches, `git clean -f`, `git checkout --` on dirty files.
- `rm -rf` outside the agent's own worktree.
- Bulk-mutating scripts (anything that updates more than a handful of files automatically).
- Deleting tracker entries or rewriting the decisions log.
- Posting / commenting / sending to external systems (GitHub PRs, Slack, email) on behalf of the user.
- Modifying CI/CD, secrets, env vars.

**Rules of engagement** (same as global):
1. **Scope is literal and narrow.** "Yes" to writing a script is **not** "yes" to running it.
2. **Write the script, present it, stop.** Phrasing: "Wrote `script.py` that will [exact effect]. Run it?" — then wait.
3. **Default to read-only / dry-run** when investigating.
4. **Past approval doesn't carry forward.** Re-running the same script later requires fresh approval.
5. **When in doubt, ask.** Cost of one extra question is trivial.

---

## 7. Update protocol

After any non-trivial work:

1. Run the relevant smoke test from `docs/smoke-tests.md` and confirm it passes. Type-check + unit-test alone are **not** enough to claim done.
2. Update `docs/PROJECT_TRACKER.md`:
   - Move the task to **Done** with date + PR/commit link.
   - Add follow-ups to **Ready to claim** with a one-line note.
3. If you made an architectural choice not already in the design doc, append to the **Decisions log** with date, decision, rationale, reversibility.
4. Commit the tracker update as the final commit in your branch (or as a separate commit on `main` if you're already merging).

This is the handoff — the next agent reads only the tracker to know where to start.

---

## 8. What this slice is, and is not

**Is:** P0–P5 of the MVP slice in `docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md` — viewer + upload + parser + dashboard + sequence panel + DB import. No auth, no DB, no AI, no mutation, no export.

**Is not:** the full 6-month platform. Anything outside the slice (AI assistant, mutation, comparison, export, similarity search, auth, persistence, DSSP, Docker, deployment) belongs to a future slice with its own spec. If a task implies we need one of those, **stop and tell the user** — do not silently expand scope.

---

## 9. Quick reference

- **Source spec:** `docs/spec.md`
- **SDLC plan:** `docs/sdlc.md`
- **Active slice design:** `docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md`
- **Tracker (read + update every task):** `docs/PROJECT_TRACKER.md`
- **Smoke tests:** `docs/smoke-tests.md` (created in P0)
- **Owner's working rules:** destructive-action gate (do-or-die rule), parallel-agents preference, commit authorship — all defined in this file.
