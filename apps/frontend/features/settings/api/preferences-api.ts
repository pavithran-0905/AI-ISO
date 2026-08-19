/**
 * `services/user-management-service` — `/users/preferences`,
 * `/users/profile`, `/users/{id}` (self-edit only, see
 * `PatchUserIdentityInput`'s own docstring on the missing ownership
 * check this module deliberately never exploits).
 */

import { apiClient } from "@/api/client";
import type {
  PatchUserIdentityInput,
  UpdateUserPreferencesInput,
  UpdateUserProfileInput,
  UserPreferences,
  UserProfile,
} from "@/features/settings/types";

interface PreferencesResponseBody {
  user_id: string;
  language: string;
  theme: string;
  timezone: string;
  date_format: string;
  time_format: string;
  dashboard_preferences: Record<string, unknown>;
  notification_preferences: Record<string, unknown>;
  accessibility: Record<string, unknown>;
  default_organization_id: string | null;
  default_project_id: string | null;
}

function toPreferences(body: PreferencesResponseBody): UserPreferences {
  return {
    userId: body.user_id,
    language: body.language,
    theme: body.theme,
    timezone: body.timezone,
    dateFormat: body.date_format,
    timeFormat: body.time_format,
    dashboardPreferences: body.dashboard_preferences,
    notificationPreferences: body.notification_preferences,
    accessibility: body.accessibility,
    defaultOrganizationId: body.default_organization_id,
    defaultProjectId: body.default_project_id,
  };
}

interface ProfileResponseBody {
  user_id: string;
  biography: string | null;
  job_title: string | null;
  department: string | null;
  employee_id: string | null;
  manager_id: string | null;
  custom_fields: Record<string, unknown>;
  profile_photo: string | null;
}

function toProfile(body: ProfileResponseBody): UserProfile {
  return {
    userId: body.user_id,
    biography: body.biography,
    jobTitle: body.job_title,
    department: body.department,
    employeeId: body.employee_id,
    managerId: body.manager_id,
    customFields: body.custom_fields,
    profilePhoto: body.profile_photo,
  };
}

export const preferencesApi = {
  async getPreferences(): Promise<UserPreferences> {
    const body = await apiClient.get<PreferencesResponseBody>("/users/preferences");
    return toPreferences(body);
  },

  /** Full-replace `PUT` (confirmed: no `PATCH` route exists) — always
   * pass the complete, currently-known object, never a partial diff. */
  async updatePreferences(input: UpdateUserPreferencesInput): Promise<UserPreferences> {
    const body = await apiClient.put<PreferencesResponseBody>("/users/preferences", {
      language: input.language,
      theme: input.theme,
      timezone: input.timezone,
      date_format: input.dateFormat,
      time_format: input.timeFormat,
      dashboard_preferences: input.dashboardPreferences,
      notification_preferences: input.notificationPreferences,
      accessibility: input.accessibility,
      default_organization_id: input.defaultOrganizationId,
      default_project_id: input.defaultProjectId,
    });
    return toPreferences(body);
  },

  async getProfile(): Promise<UserProfile> {
    const body = await apiClient.get<ProfileResponseBody>("/users/profile");
    return toProfile(body);
  },

  /** Full-replace `PUT` — same reasoning as `updatePreferences`. */
  async updateProfile(input: UpdateUserProfileInput): Promise<UserProfile> {
    const body = await apiClient.put<ProfileResponseBody>("/users/profile", {
      biography: input.biography,
      job_title: input.jobTitle,
      department: input.department,
      employee_id: input.employeeId,
      manager_id: input.managerId,
      custom_fields: input.customFields,
    });
    return toProfile(body);
  },

  /** `PATCH /users/{id}` — genuinely partial. `userId` must always be
   * the caller's own id (from `useSession`), never user-suppliable —
   * see the type's own docstring for why. */
  async patchIdentity(userId: string, input: PatchUserIdentityInput): Promise<void> {
    await apiClient.patch(`/users/${userId}`, {
      display_name: input.displayName,
      first_name: input.firstName,
      middle_name: input.middleName,
      last_name: input.lastName,
      phone_number: input.phoneNumber,
    });
  },
};
