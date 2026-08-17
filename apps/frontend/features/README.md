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

**Nothing lives here yet.** docs/frontend Prompt 001 §9/§34 explicitly
forbids implementing business-module screens in the foundation prompt —
this file exists only to establish the pattern every subsequent frontend
prompt will follow.

`modules/dashboard/` (the existing placeholder proving the platform's
presentation layer works end-to-end against the gateway) predates this
convention and is intentionally left in place rather than migrated here —
see docs/frontend/README.md for why.
