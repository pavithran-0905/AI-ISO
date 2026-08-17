# Frontend Architecture

## Stack

Next.js 16 (App Router, Turbopack) + React 19 + TypeScript (strict) +
Tailwind CSS v4 + TanStack Query + Zustand + React Hook Form + Zod +
Vitest + Testing Library + Playwright. See `docs/frontend/README.md`
for why this differs from Prompt 001's literal Vite/React Router
baseline.

## Layering

```
Application (app/layout.tsx, providers/)
    ↓
Pages (app/**/page.tsx — route-group layout wraps them in a Layout)
    ↓
Features (features/<feature>/pages, once features exist)
    ↓
Shared components (components/ui, data-display, feedback, forms, navigation, overlays)
    ↓
Foundation (api/, auth/, permissions/, state/, layouts/, lib/, utils/, config/)
```

API access follows, without exception:

```
Page/Component → feature hook (TanStack Query) → feature API function → @/api/client → HTTP → backend
```

`@/api/client` (`apps/frontend/api/client.ts`) is the **only** module
allowed to call `fetch()`. Nothing else does — not a component, not a
hook, not a Zustand store.

## Why Next.js App Router instead of Vite + React Router

The existing `apps/frontend` was already built on Next.js before this
prompt began (see `docs/frontend/README.md`). Beyond "already there,"
it satisfies everything Prompt 001 actually wants from routing:
file-system routing, route groups for layout composition
(`app/(app)/layout.tsx`), built-in `not-found.tsx`/`error.tsx`/
`global-error.tsx` conventions, and static/server rendering for a
premium, fast-loading enterprise app. Adding React Router on top would
mean running two routers.

## What's foundation vs. what's a future prompt

Built now: the API client, auth/permission architecture, route
groups + metadata registry, six reusable layouts, the completed design
token set, loading/empty/error/offline/access-denied primitives, and
the testing setup for all of it.

Not built now (Prompt 001 §9/§34 forbids it): any business-module
screen. The next frontend prompt is expected to build the first real
feature inside `features/<feature>/`, using everything documented here.
