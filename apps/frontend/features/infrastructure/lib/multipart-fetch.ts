/**
 * A small, deliberately separate fetch path for `POST /inventory/import`
 * — the one route in this feature that takes a `multipart/form-data`
 * body (a real file upload) rather than JSON, which `@/api/client`
 * doesn't support (confirmed: it always serializes `options.body` as
 * JSON and sets `Content-Type: application/json`). Mirrors that
 * client's own auth/error-normalization behavior (same
 * `ApiRequestError`/`ApiNetworkError` types, same envelope parsing,
 * same unauthorized-handler wiring) so callers handle failures
 * identically either way — matches the precedent
 * `features/reporting/lib/binary-fetch.ts` set for binary downloads.
 */

import { getAccessToken } from "@/auth/store";
import { env } from "@/config/env";
import { ApiNetworkError, ApiRequestError } from "@/api/client";
import type { ApiResponse } from "@/types/api";

async function parseErrorBody(response: Response): Promise<{ message: string; code: string; details: string[] }> {
  try {
    const body = (await response.json()) as ApiResponse<unknown>;
    if (!body.success) {
      return { message: body.message, code: body.error.code, details: body.error.details };
    }
    return { message: response.statusText, code: "AIIOS-UNKNOWN", details: [] };
  } catch {
    return { message: response.statusText || "Upload failed.", code: "AIIOS-UNKNOWN", details: [] };
  }
}

/** `path` includes the query string — `POST /inventory/import`'s
 * `organization_id`/`source_format`/`preview_only` are all real query
 * params on this route, not multipart fields (confirmed by source
 * inspection); `file` is the only actual form field. */
export async function postMultipart<TData>(path: string, file: File): Promise<TData> {
  const headers: Record<string, string> = { "X-Request-ID": crypto.randomUUID() };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const formData = new FormData();
  formData.append("file", file);

  let response: Response;
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, { method: "POST", headers, body: formData });
  } catch (cause) {
    throw new ApiNetworkError(path, cause);
  }

  if (!response.ok) {
    const { message, code, details } = await parseErrorBody(response);
    throw new ApiRequestError(response.status, message, code, details);
  }

  const body = (await response.json()) as ApiResponse<TData>;
  if (!body.success) {
    throw new ApiRequestError(response.status, body.message, body.error.code, body.error.details);
  }
  return body.data;
}
