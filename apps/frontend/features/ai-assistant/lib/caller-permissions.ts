import { canPerform, PERMISSION_ACTIONS } from "@/permissions";
import type { Role } from "@/auth/types";

/**
 * Populates `SendMessageInput.callerPermissions` from the existing
 * coarse capability model, purely for consistency with every other
 * feature's own permission gating — see that field's own docstring
 * (`features/ai-assistant/types/index.ts`) and
 * `docs/frontend/backend-v1-integration-limitations.md`: the backend
 * trusts this list with NO cross-check against the caller's real
 * JWT-derived role, so it is never a security boundary here either.
 */
export function derivedCallerPermissions(role: Role | null): string[] {
  return PERMISSION_ACTIONS.filter((action) => canPerform(role, action));
}
