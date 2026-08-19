import type { UserStatusValue } from "@/features/administration/types";
import type { StatusState } from "@/lib/status";

/** `UserStatus` — a real account-lifecycle vocabulary, mapped onto
 * the canonical `StatusState` taxonomy for `StatusIndicator`. */
export const USER_STATUS_TO_STATE: Record<UserStatusValue, StatusState> = {
  pending: "pending",
  invited: "pending",
  active: "healthy",
  inactive: "stopped",
  locked: "critical",
  disabled: "stopped",
  deleted: "cancelled",
  archived: "stopped",
  suspended: "critical",
};
