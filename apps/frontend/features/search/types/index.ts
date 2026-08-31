/**
 * There is no global search API anywhere in AI-IOS's backend
 * (confirmed absent, per Prompt 003's own already-documented finding
 * in `docs/frontend/backend-v1-integration-limitations.md`). This
 * feature composes calls to existing, already-built feature API
 * modules — never a new HTTP call, never a fabricated single backend
 * "search" capability. See `docs/frontend/developer-guide/global-search.md`
 * for the exact per-resource-type strategy (real server-side search
 * for the two resources that support it; client-side filtering over
 * an already-fetched, org-scoped list for the rest, since none of
 * their real list routes accepts a free-text query parameter).
 */

/** Only resource types with a real, already-built list/search API
 * this session's own prior prompts established. Audit events and
 * notifications are deliberately excluded — confirmed absent of any
 * free-text-searchable field on any of their real routes (see the
 * developer guide) — never approximated by matching on an unrelated
 * exact-match field. */
export const SEARCH_RESULT_TYPES = ["asset", "user", "alert", "automation", "report", "conversation"] as const;
export type SearchResultType = (typeof SEARCH_RESULT_TYPES)[number];

export const SEARCH_RESULT_TYPE_LABELS: Record<SearchResultType, string> = {
  asset: "Assets",
  user: "Users",
  alert: "Alerts",
  automation: "Automations",
  report: "Reports",
  conversation: "AI Conversations",
};

/** The normalized shape every adapter (`features/search/lib/adapters.ts`)
 * maps a real feature's own domain model into — UI components depend
 * only on this, never on any one feature's own response shape (§41). */
export interface SearchResult {
  id: string;
  resultType: SearchResultType;
  title: string;
  description: string | null;
  status: string | null;
  href: string;
}

export interface SearchResultGroup {
  type: SearchResultType;
  label: string;
  results: SearchResult[];
  isLoading: boolean;
  /** True when this one group's own source query failed — the rest of
   * the groups must still render (§33/§34's "partial search failure"). */
  isError: boolean;
}
