/**
 * Permission types mirroring `shared_core.enums.permission.Permission`
 * (the 9 actions actually embedded in backend authorization checks) and
 * `shared_core.enums.role.Role` (re-exported from `@/auth/types`).
 *
 * `services/rbac-service` separately models fine-grained
 * resource+action+scope permission triples
 * (`services/rbac-service/app/models/permission.py`), but nothing in the
 * running backend calls that service at request time — every service
 * (api-gateway-service, secrets-management-service, project-service,
 * organization-service) enforces authorization locally against the
 * caller's own decoded JWT `role` claim, per direct source inspection.
 * The frontend therefore has no live endpoint to resolve a user's actual
 * fine-grained permission set, and this module does not invent one — see
 * `@/permissions/capabilities` for the resulting, deliberately coarse
 * model and docs/frontend/architecture/authorization.md for the full
 * rationale.
 */

export const PERMISSION_ACTIONS = [
  "read",
  "create",
  "update",
  "delete",
  "execute",
  "approve",
  "export",
  "import",
  "admin",
] as const;

export type PermissionAction = (typeof PERMISSION_ACTIONS)[number];

export type { Role } from "@/auth/types";
