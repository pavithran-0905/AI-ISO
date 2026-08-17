# Authorization

## The real backend model

`services/rbac-service` models fine-grained permissions as
resource+action+scope triples (`app/models/permission.py`) and
hierarchical roles (`app/models/role.py`). **Nothing in the running
backend calls it at request time**, per direct source inspection of
`services/api-gateway-service`, `services/secrets-management-service`,
`services/project-service`, and `services/organization-service`: every
one of them enforces authorization locally against the caller's own
decoded JWT claims, not a live `rbac-service` lookup. The 6 fixed roles
(`shared_core.enums.role.Role`: `super_admin`, `organization_admin`,
`project_admin`, `operator`, `viewer`, `auditor`) and 9 actions
(`shared_core.enums.permission.Permission`: `read`, `create`, `update`,
`delete`, `execute`, `approve`, `export`, `import`, `admin`) are what's
actually embedded in and checked against JWTs.

The frontend therefore has **no live source for a user's fine-grained
permission set** — only, when present, a single `role` claim (see
`authentication.md` for why it's frequently absent today).
`permissions/types.ts` documents this explicitly rather than inventing
a permission-fetching endpoint that doesn't exist.

## The resulting model: coarse, role-only, presentation-only

`permissions/capabilities.ts`'s `canPerform(role, action)` maps each of
the 6 roles to the subset of the 9 actions it's granted, as a
**deliberately coarse heuristic** — not a reconstruction of
`rbac-service`'s real resource+action+scope model, since the frontend
has no data to reconstruct it from. A `null` role (the common case
today) is treated as read-only.

**This grants no security whatsoever.** Every `RequireRole`/
`RequirePermission` (`permissions/guards.tsx`) or `usePermissions()`/
`useHasRole()` (`permissions/hooks.ts`) check exists purely so the UI
doesn't show a control that would just produce a backend 403 — saving
the user a wasted click, nothing more. The backend remains the sole
authority on every request, independent of anything the frontend
decided to render. This is stated directly in the module docstrings of
every file in `permissions/`, not just here.

## Where this shows up

- **Component-level**: `<RequirePermission action="delete">` around a
  destructive button.
- **Route-level**: not yet wired (no protected route exists yet — see
  `authentication.md`), but the same `RequireRole` component is meant
  to gate an entire route's content once one does.
- **Action-level**: the same `RequirePermission`, scoped around a
  single button/menu item rather than a whole page.

No page-level or action-level gating exists in the shipped app yet,
since no business page exists yet (Prompt 001 §34). The primitives are
built and tested (`tests/unit/permissions/`); the first feature to need
them wires them in.
