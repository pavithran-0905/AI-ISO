"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import { Alert } from "@/components/feedback/alert";
import { EmptyState } from "@/components/feedback/empty-state";
import { PageHeader } from "@/components/navigation/page-header";
import { AdministrationSubNav } from "@/features/administration/components/administration-sub-nav";
import { EMPTY_USER_FILTERS, UserFilters, type UserFilterValues } from "@/features/administration/components/user-filters";
import { UserTable } from "@/features/administration/components/user-table";
import { useUserSearch } from "@/features/administration/hooks/use-users";
import type { UserStatusValue } from "@/features/administration/types";
import { SectionState } from "@/features/dashboard/components/section-state";

const PAGE_SIZE = 25;

function hasActiveFilters(filters: UserFilterValues): boolean {
  return Boolean(filters.query || filters.status);
}

/**
 * Users — `/administration/users` (§6). **No route in
 * `user-management-service` enforces any permission check** —
 * confirmed by direct source inspection, any valid JWT can list/
 * search/view/edit/status-transition/delete any user. This page is
 * only reachable from the nav for administrators (`lib/route-registry.ts`'s
 * `roles` restriction), but that's a frontend-side tightening, not a
 * real security boundary — the banner below says so plainly, not just
 * in code comments.
 */
export function UsersListPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const filters: UserFilterValues = useMemo(
    () => ({
      query: searchParams.get("q") ?? EMPTY_USER_FILTERS.query,
      status: (searchParams.get("status") as UserStatusValue | null) ?? EMPTY_USER_FILTERS.status,
    }),
    [searchParams],
  );
  const page = Number(searchParams.get("page") ?? "1") || 1;

  const updateParams = useCallback(
    (next: Partial<{ q: string; status: string; page: string }>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(next)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      router.push(`/administration/users?${params.toString()}`);
    },
    [router, searchParams],
  );

  const query = useUserSearch({
    query: filters.query || undefined,
    status: filters.status || undefined,
    page,
    pageSize: PAGE_SIZE,
  });

  function handleFiltersChange(next: UserFilterValues) {
    updateParams({ q: next.query, status: next.status, page: "" });
  }

  function handleReset() {
    updateParams({ q: "", status: "", page: "" });
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Users" description="Every user account known to AI-IOS." />
      <AdministrationSubNav />

      <Alert tone="warning" title="This service enforces no access control on its own">
        Any signed-in user can call these same APIs directly to view or change any account. This page&apos;s own visibility
        and controls are a convenience, not a security boundary — see the developer guide.
      </Alert>

      <UserFilters values={filters} onChange={handleFiltersChange} onReset={handleReset} />

      <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-96 w-full">
        {query.data &&
          (query.data.items.length === 0 ? (
            <EmptyState
              title={hasActiveFilters(filters) ? "No matching users" : "No users found"}
              description={hasActiveFilters(filters) ? "Try a different search term or clear filters." : "No users are registered yet."}
            />
          ) : (
            <UserTable result={query.data} onPageChange={(nextPage) => updateParams({ page: String(nextPage) })} />
          ))}
      </SectionState>
    </div>
  );
}
