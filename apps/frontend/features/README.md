# Feature modules

Every future business module (dashboard, monitoring, alerting, reporting,
ai-assistant, automation, users, rbac, secrets, projects, observability,
analytics, audit, notifications, release-distribution, ...) lives here,
one directory per feature, each following the same internal shape:

```
features/<feature>/
├── api/          # feature-level API functions, calling @/api/client — never fetch() directly
├── components/   # feature-specific UI (not generic — see components/ for that)
├── hooks/        # feature-specific hooks (TanStack Query wrappers, derived state)
├── pages/        # composed page components, rendered by an app/**/page.tsx
├── schemas/      # Zod schemas for this feature's forms/API payloads
├── stores/       # Zustand stores, only for genuine client state (see docs/frontend/architecture/state-management.md)
├── types/        # this feature's own types
├── utils/        # this feature's own pure helpers
├── tests/        # unit/component tests for this feature
└── index.ts      # the feature's public surface — nothing outside imports past this file
```

**`dashboard/` is the first real occupant** (Frontend Prompt 005) —
built once the dashboard became a real business feature rather than
the bootstrap placeholder `modules/dashboard/` used to be (that
directory no longer exists; it was migrated in, not left in place —
see docs/frontend/README.md and docs/frontend/developer-guide/dashboard.md).
Every subsequent business module (monitoring, alerting, reporting,
ai-assistant, automation, users, rbac, secrets, projects,
observability, analytics, audit, notifications, release-distribution,
...) follows the exact same shape.
