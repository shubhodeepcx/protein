# ProteoLens — Frontend

Next.js 16 (App Router) + TypeScript (strict) + Tailwind v4 + shadcn/ui + Zustand. This is the web UI for the AI-powered protein structure visualization platform. The corresponding API lives in [`../backend`](../backend) and is expected to run on `http://localhost:8000`.

## Quick start

```powershell
# from this directory
npm install
npm run dev
```

The dev server starts on `http://localhost:3000`. On first load it pings `GET /health` on the backend; the pill in the top-right shows green if the backend is up, red otherwise.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the Next.js dev server on `:3000` (Turbopack). |
| `npm run build` | Production build. |
| `npm run start` | Run the production build. |
| `npm run lint` | TypeScript-only check (`tsc --noEmit`). |
| `npm test` | Run the Vitest suite once. |
| `npm run test:watch` | Vitest in watch mode. |

## Environment variables

Copy `.env.local.example` to `.env.local` and edit as needed.

| Variable | Default | Description |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL for the FastAPI backend. |

## Layout

`app/page.tsx` renders the workspace shell described in the spec (`docs/superpowers/specs/2026-05-23-protein-mvp-slice-design.md`, section 4.1):

- Top header (`h-14`): app title, global search placeholder, backend health pill, upload button.
- Left column (`w-72`): chain / residue sidebar placeholder.
- Center column: Mol* viewer placeholder card (real viewer arrives in P1).
- Right column (`w-96`): tabbed panel — Overview / Sequence / Analytics (real content in P3 / P4).

## State

`lib/store/` holds the Zustand slices from spec section 4.2:

- `protein-slice.ts` — current `ProteinSummary` + `loadProtein(id)` stub.
- `selection-slice.ts` — selected residue keys + `toggleResidue(key)`.
- `viewer-slice.ts` — Mol* representation + coloring + camera reset signal.
- `index.ts` — composes the three slices into a single `useStore` hook.

## Testing

Vitest + `@testing-library/react` + jsdom. Smoke test for the selection slice lives at `lib/store/__tests__/selection-slice.test.ts`. New modules should ship with at least one Vitest spec under `__tests__/` or alongside the file as `*.test.ts(x)`.

## Status

P0 — Scaffold only. No Mol*, no upload, no API calls beyond the health probe. See `../docs/PROJECT_TRACKER.md` for the active phase backlog.
