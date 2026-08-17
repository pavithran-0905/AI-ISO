# AI-IOS Frontend Developer Guide (structure only)

Per Prompt 001 §27, this prompt establishes the structure only, backed
by the real `architecture/` and `standards/` documents already written
for this prompt.

## Getting started (today's actual instructions)

```bash
cd apps/frontend
pnpm install       # from the repo root, or here — it's a pnpm workspace member
pnpm dev            # requires services/api-gateway-service running; see .env.example
pnpm typecheck
pnpm lint
pnpm test
pnpm test:coverage
pnpm test:e2e       # requires `pnpm exec playwright install` once
pnpm build
```

See `apps/frontend/README.md` for the authoritative, up-to-date version
of this — this file exists to establish the doc structure, not to
duplicate and drift from it.

## Where to go next

- Adding a new generic component → `standards/component-guidelines.md`.
- Adding a new business feature → `apps/frontend/features/README.md`
  (the pattern) once Prompt 001's foundation is in use by a real
  feature prompt.
- Understanding why something is built the way it is → `architecture/`,
  which is written to explain *why*, not just *what*.

## Planned sections (not yet written)

- Local environment setup beyond the commands above (backend service
  dependencies, seed data).
- Debugging guide (React DevTools, TanStack Query DevTools — not yet
  installed).
- Release/deployment process for the frontend specifically.
- Contribution workflow (PR conventions, review checklist).
