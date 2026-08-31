"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { usePermissions } from "@/permissions/hooks";
import { chatApi } from "@/features/ai-assistant/api/chat-api";
import { alertsApi } from "@/features/alerting/api/alerts-api";
import { usersApi } from "@/features/administration/api/users-api";
import { jobsApi } from "@/features/automation/api/jobs-api";
import { assetsApi } from "@/features/infrastructure/api/assets-api";
import { reportsApi } from "@/features/reporting/api/reports-api";
import { alertToResult, assetToResult, automationToResult, conversationToResult, reportToResult, userToResult } from "@/features/search/lib/adapters";
import { rankResults } from "@/features/search/lib/rank";
import type { SearchResultGroup } from "@/features/search/types";
import { useDebouncedValue } from "@/lib/use-debounced-value";
import { useSelectedOrganization } from "@/organization/use-organizations";

const MIN_QUERY_LENGTH = 2;
const DEFAULT_RESULTS_PER_GROUP = 5;
const DEBOUNCE_MS = 200;

function matchesQuery(haystack: string | null, query: string): boolean {
  return haystack !== null && haystack.toLowerCase().includes(query);
}

/**
 * Composes existing, already-built feature API modules — never a new
 * HTTP call, never a fabricated single backend "search" (§4/§40).
 *
 * Two real strategies, per what each resource's actual list route
 * supports (confirmed by source inspection, cited in each API module's
 * own docstring):
 * - **Assets** (`GET /inventory/search`) and **Users**
 *   (`POST /users/search`) accept a real free-text `query` parameter —
 *   genuine, debounced, server-side search, re-fetched per keystroke
 *   (TanStack Query's own query-key change naturally discards a stale
 *   in-flight response — §32).
 * - **Alerts**, **Automations**, **Reports**, **AI Conversations**
 *   have no free-text query parameter on their real list routes at
 *   all (confirmed absent on each) — this feature fetches each
 *   organization-scoped list once (cached, not re-fetched per
 *   keystroke — §31's "do not trigger an API request on every
 *   keystroke") and filters client-side by title/description
 *   substring, exactly the same pattern already established in
 *   `features/reporting/pages/reports-list-page.tsx`.
 *
 * Users results are gated to administrative sessions only — the same
 * convenience Users' own nav entry already applies, never a fix for
 * that service's own confirmed lack of server-side authorization
 * (Prompt 014).
 */
export function useGlobalSearch(rawQuery: string, active: boolean, resultsPerGroup: number = DEFAULT_RESULTS_PER_GROUP) {
  const { selectedOrganizationId } = useSelectedOrganization();
  const { isAdministrative } = usePermissions();
  const debouncedQuery = useDebouncedValue(rawQuery, DEBOUNCE_MS);
  const query = debouncedQuery.trim().toLowerCase();
  const queryLongEnough = query.length >= MIN_QUERY_LENGTH;
  const orgReady = selectedOrganizationId !== null;

  const assetsQuery = useQuery({
    queryKey: ["search", "assets", selectedOrganizationId, query, resultsPerGroup],
    queryFn: () => assetsApi.search({ organizationId: selectedOrganizationId as string, query, page: 1, pageSize: resultsPerGroup }),
    enabled: active && orgReady && queryLongEnough,
    staleTime: 15_000,
  });

  const usersQuery = useQuery({
    queryKey: ["search", "users", query, resultsPerGroup],
    queryFn: () => usersApi.search({ query, page: 1, pageSize: resultsPerGroup }),
    enabled: active && isAdministrative && queryLongEnough,
    staleTime: 15_000,
  });

  const alertsListQuery = useQuery({
    queryKey: ["search", "alerts-all", selectedOrganizationId],
    queryFn: () => alertsApi.list({ organizationId: selectedOrganizationId as string }),
    enabled: active && orgReady && queryLongEnough,
    staleTime: 60_000,
  });

  const automationsListQuery = useQuery({
    queryKey: ["search", "automations-all", selectedOrganizationId],
    queryFn: () => jobsApi.list(selectedOrganizationId as string),
    enabled: active && orgReady && queryLongEnough,
    staleTime: 60_000,
  });

  const reportsListQuery = useQuery({
    queryKey: ["search", "reports-all", selectedOrganizationId],
    queryFn: () => reportsApi.list({ organizationId: selectedOrganizationId as string }),
    enabled: active && orgReady && queryLongEnough,
    staleTime: 60_000,
  });

  /** `mineOnly: true` — never another user's conversations (§22). */
  const conversationsListQuery = useQuery({
    queryKey: ["search", "conversations-all", selectedOrganizationId],
    queryFn: () => chatApi.listConversations(selectedOrganizationId as string, true),
    enabled: active && orgReady && queryLongEnough,
    staleTime: 60_000,
  });

  const groups: SearchResultGroup[] = useMemo(() => {
    if (!queryLongEnough) return [];

    const list: SearchResultGroup[] = [
      {
        type: "asset",
        label: "Assets",
        results: rankResults((assetsQuery.data?.items ?? []).map(assetToResult), query),
        isLoading: assetsQuery.isLoading,
        isError: assetsQuery.isError,
      },
      {
        type: "alert",
        label: "Alerts",
        results: rankResults(
          (alertsListQuery.data ?? []).filter((alert) => matchesQuery(alert.title, query) || matchesQuery(alert.message, query)).map(alertToResult).slice(0, resultsPerGroup),
          query,
        ),
        isLoading: alertsListQuery.isLoading,
        isError: alertsListQuery.isError,
      },
      {
        type: "automation",
        label: "Automations",
        results: rankResults(
          (automationsListQuery.data ?? [])
            .filter((job) => matchesQuery(job.name, query) || matchesQuery(job.description, query))
            .map(automationToResult)
            .slice(0, resultsPerGroup),
          query,
        ),
        isLoading: automationsListQuery.isLoading,
        isError: automationsListQuery.isError,
      },
      {
        type: "report",
        label: "Reports",
        results: rankResults(
          (reportsListQuery.data ?? [])
            .filter((report) => matchesQuery(report.name, query) || matchesQuery(report.description, query))
            .map(reportToResult)
            .slice(0, resultsPerGroup),
          query,
        ),
        isLoading: reportsListQuery.isLoading,
        isError: reportsListQuery.isError,
      },
      {
        type: "conversation",
        label: "AI Conversations",
        results: rankResults(
          (conversationsListQuery.data ?? []).filter((conversation) => matchesQuery(conversation.title, query)).map(conversationToResult).slice(0, resultsPerGroup),
          query,
        ),
        isLoading: conversationsListQuery.isLoading,
        isError: conversationsListQuery.isError,
      },
    ];

    if (isAdministrative) {
      list.splice(1, 0, {
        type: "user",
        label: "Users",
        results: rankResults((usersQuery.data?.items ?? []).map(userToResult), query),
        isLoading: usersQuery.isLoading,
        isError: usersQuery.isError,
      });
    }

    return list.filter((group) => group.results.length > 0 || group.isLoading || group.isError);
  }, [
    queryLongEnough,
    query,
    resultsPerGroup,
    isAdministrative,
    assetsQuery.data,
    assetsQuery.isLoading,
    assetsQuery.isError,
    usersQuery.data,
    usersQuery.isLoading,
    usersQuery.isError,
    alertsListQuery.data,
    alertsListQuery.isLoading,
    alertsListQuery.isError,
    automationsListQuery.data,
    automationsListQuery.isLoading,
    automationsListQuery.isError,
    reportsListQuery.data,
    reportsListQuery.isLoading,
    reportsListQuery.isError,
    conversationsListQuery.data,
    conversationsListQuery.isLoading,
    conversationsListQuery.isError,
  ]);

  const isSearching = queryLongEnough && groups.some((group) => group.isLoading);

  return { groups, isSearching, queryLongEnough, orgReady };
}
