# AI-IOS Frontend Documentation

This tree documents the Enterprise Frontend built against Frontend
Prompt 001 (`docs/frontend/001-enterprise-frontend-architecture.txt`).

## A pre-existing foundation, adopted rather than replaced

Frontend Prompt 001 mandates a new top-level `frontend/` application on
Vite + React Router. When work on it began, the repository already
contained a working frontend at `apps/frontend/` — built earlier against
`docs/009_Frontend_Master_Architecture.md.txt`,
`docs/010_UI_UX_Design_System_Master.md.txt`, and
`docs/011_Project_Bootstrap.md.txt` — on **Next.js 16 (App Router) +
React 19**, with TanStack Query, Zustand, React Hook Form, Zod,
Tailwind CSS v4, Vitest, Testing Library, and Playwright already wired
up, plus a `pnpm` workspace (`apps/*`, `packages/*`) already in place at
the repository root.

Per an explicit decision (Prompt 001 itself anticipates finding an
existing frontend and says to "decide exact integration with the
existing repository" rather than prescribing an answer), that existing
application was **adopted as the foundation**, not replaced:

- **Location**: `apps/frontend/`, not a new top-level `frontend/` — matching
  the repository's own established `apps/*` workspace convention.
- **Framework**: Next.js App Router, not Vite + React Router. Next.js
  *is* the router (file-system routing, route groups, layouts, built-in
  `not-found.tsx`/`error.tsx` conventions) — there is no separate
  React Router to add on top of it.
- **The existing `modules/dashboard/` placeholder was left in place,
  untouched.** It proves the platform's presentation layer works
  end-to-end against the gateway (health check → rendered card) and
  predates the `features/` convention this prompt establishes for every
  *future* business module — see `features/README.md` in the app.

Every other section of Prompt 001 (API architecture, auth/RBAC
foundation, routing/permission metadata, layouts, design tokens,
loading/empty/error states, testing foundation) was implemented fresh
against the real, already-running backend — see `architecture/` for
what was built and why, and `backend-feature-matrix.md` for what the
running backend (Prompts 000-080) actually exposes.

## Structure

- `architecture/` — how the frontend is built: folder structure,
  dependency boundaries, API/state/auth/authorization/routing/error
  architecture.
- `standards/` — how to write frontend code here: coding standards,
  naming, component guidelines, accessibility, responsive design,
  performance, testing.
- `backend-feature-matrix.md` — for every backend Prompt 000-080, what
  it exposes and what frontend feature (if any) consumes it, with
  honest `IMPLEMENTED` / `PLANNED` / `UNKNOWN — VERIFY` status per row.
- `user-guide/` — structure for future end-user documentation.
- `developer-guide/` — structure for future contributor documentation.
- `rfi/` — structure for future RFI/RFP submission material.

## What exists today vs. what's foundation-only

Per Prompt 001 §34, no business-module screens were built. What exists
is the **foundation**: the API client, the auth/permission architecture
(built against the real, verified backend contract — including a
documented backend gap, see `architecture/authentication.md`), the
route/layout/design-token/error-state scaffolding, and the one
pre-existing placeholder page (the dashboard). Every future business
module (monitoring, alerting, reporting, ...) will be built inside
`features/<feature>/` following the pattern in `apps/frontend/features/README.md`.
