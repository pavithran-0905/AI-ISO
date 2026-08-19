/**
 * `services/user-management-service` — `/users`, `/users/search`,
 * `/users/{id}`, `/users/{id}/notes`. **No route in this entire
 * service enforces any role/permission check** (confirmed absent by
 * source inspection) — any valid JWT can list/search/view/edit/
 * status-transition/delete any user. See the developer guide's
 * prominent warning; this frontend gates its own controls with the
 * existing coarse `isAdministrative` heuristic as a UX convenience
 * only, never a security boundary.
 */

import { apiClient } from "@/api/client";
import type { AdminNote, PatchUserInput, UserDetail, UserSearchParams, UserSearchResult, UserSummary } from "@/features/administration/types";

interface UserSummaryBody {
  id: string;
  username: string;
  email: string;
  display_name: string | null;
  avatar: string | null;
  status: string;
  created_at: string;
}

function toSummary(body: UserSummaryBody): UserSummary {
  return {
    id: body.id,
    username: body.username,
    email: body.email,
    displayName: body.display_name,
    avatar: body.avatar,
    status: body.status as UserSummary["status"],
    createdAt: body.created_at,
  };
}

interface UserDetailBody {
  id: string;
  username: string;
  email: string;
  display_name: string | null;
  first_name: string | null;
  middle_name: string | null;
  last_name: string | null;
  phone_number: string | null;
  avatar: string | null;
  timezone: string;
  language: string;
  locale: string;
  status: string;
  last_login: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

function toDetail(body: UserDetailBody): UserDetail {
  return {
    id: body.id,
    username: body.username,
    email: body.email,
    displayName: body.display_name,
    firstName: body.first_name,
    middleName: body.middle_name,
    lastName: body.last_name,
    phoneNumber: body.phone_number,
    avatar: body.avatar,
    timezone: body.timezone,
    language: body.language,
    locale: body.locale,
    status: body.status as UserDetail["status"],
    lastLogin: body.last_login,
    metadata: body.metadata,
    createdAt: body.created_at,
    updatedAt: body.updated_at,
  };
}

interface NoteBody {
  id: string;
  author_id: string;
  body: string;
  created_at: string;
}

const DEFAULT_PAGE_SIZE = 25;

export const usersApi = {
  /** `POST /users/search` — the only route with a real, working query
   * filter (`status`; free-text `query` over username/email/phone/
   * display name). `GET /users` (no params beyond page/pageSize) is
   * used only when no query/status is set, for a marginally simpler
   * request. Neither route's response includes a total count
   * (confirmed dropped by the backend route) — `hasMore` is a
   * heuristic. */
  async search(params: UserSearchParams): Promise<UserSearchResult> {
    const page = params.page ?? 1;
    const pageSize = params.pageSize ?? DEFAULT_PAGE_SIZE;
    let body: UserSummaryBody[];
    if (params.query || params.status) {
      body = await apiClient.post<UserSummaryBody[]>("/users/search", {
        query: params.query || undefined,
        status: params.status || undefined,
        sort: params.sort || undefined,
        page,
        page_size: pageSize,
      });
    } else {
      const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      body = await apiClient.get<UserSummaryBody[]>(`/users?${query.toString()}`);
    }
    return { items: body.map(toSummary), page, pageSize, hasMore: body.length === pageSize };
  },

  async getById(userId: string): Promise<UserDetail> {
    const body = await apiClient.get<UserDetailBody>(`/users/${userId}`);
    return toDetail(body);
  },

  /** Genuinely partial. `status` goes through the backend's own real
   * lifecycle state machine — an illegal transition returns a real
   * 409, surfaced as-is rather than pre-validated client-side (see
   * the type's own docstring). */
  async patch(userId: string, input: PatchUserInput): Promise<UserDetail> {
    const body = await apiClient.patch<UserDetailBody>(`/users/${userId}`, {
      display_name: input.displayName,
      first_name: input.firstName,
      middle_name: input.middleName,
      last_name: input.lastName,
      phone_number: input.phoneNumber,
      status: input.status,
    });
    return toDetail(body);
  },

  /** A soft delete via the row's `is_active` flag, not a `status`
   * transition to `"deleted"` (confirmed: `DELETE` calls
   * `BaseRepository.delete`, distinct from `UserService.patch`'s
   * status-transition path) — the user then 404s from every other
   * route in this service. */
  async remove(userId: string): Promise<void> {
    await apiClient.delete(`/users/${userId}`);
  },

  async listNotes(userId: string): Promise<AdminNote[]> {
    const body = await apiClient.get<NoteBody[]>(`/users/${userId}/notes`);
    return body.map((note) => ({ id: note.id, authorId: note.author_id, body: note.body, createdAt: note.created_at }));
  },

  async addNote(userId: string, noteBody: string): Promise<AdminNote> {
    const body = await apiClient.post<NoteBody>(`/users/${userId}/notes`, { body: noteBody });
    return { id: body.id, authorId: body.author_id, body: body.body, createdAt: body.created_at };
  },

  async removeNote(userId: string, noteId: string): Promise<void> {
    await apiClient.delete(`/users/${userId}/notes/${noteId}`);
  },
};
