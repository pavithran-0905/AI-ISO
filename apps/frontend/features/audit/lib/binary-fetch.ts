/**
 * `GET /compliance/reports/{id}/download` returns a raw CSV/Markdown/
 * JSON body, not the `{success, message, data, meta}` envelope
 * `@/api/client` unwraps. Mirrors the identical, already-established
 * pattern in `features/reporting/lib/binary-fetch.ts` (same
 * auth/error-normalization behavior, same `ApiRequestError`/
 * `ApiNetworkError` types) — kept as its own copy rather than a cross-
 * feature import, since Reporting and this compliance-report pipeline
 * are two separate, unrelated backend systems (see
 * `features/audit/api/audit-api.ts`'s own module docstring).
 */

import { getAccessToken } from "@/auth/store";
import { env } from "@/config/env";
import { ApiNetworkError, ApiRequestError } from "@/api/client";
import type { ApiResponse } from "@/types/api";

export interface BinaryDownload {
  blob: Blob;
  filename: string;
  contentType: string;
}

function filenameFromContentDisposition(response: Response, fallback: string): string {
  const header = response.headers.get("Content-Disposition");
  const match = header?.match(/filename="([^"]+)"/);
  return match?.[1] ?? fallback;
}

async function parseErrorBody(response: Response): Promise<{ message: string; code: string; details: string[] }> {
  try {
    const body = (await response.json()) as ApiResponse<unknown>;
    if (!body.success) {
      return { message: body.message, code: body.error.code, details: body.error.details };
    }
    return { message: response.statusText, code: "AIIOS-UNKNOWN", details: [] };
  } catch {
    return { message: response.statusText || "Download failed.", code: "AIIOS-UNKNOWN", details: [] };
  }
}

export async function fetchBinary(path: string, fallbackFilename: string): Promise<BinaryDownload> {
  const headers: Record<string, string> = { "X-Request-ID": crypto.randomUUID() };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, { method: "GET", headers });
  } catch (cause) {
    throw new ApiNetworkError(path, cause);
  }

  if (!response.ok) {
    const { message, code, details } = await parseErrorBody(response);
    throw new ApiRequestError(response.status, message, code, details);
  }

  const blob = await response.blob();
  return {
    blob,
    filename: filenameFromContentDisposition(response, fallbackFilename),
    contentType: response.headers.get("Content-Type") ?? "application/octet-stream",
  };
}

export function saveBlob(download: BinaryDownload): void {
  const url = URL.createObjectURL(download.blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = download.filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
