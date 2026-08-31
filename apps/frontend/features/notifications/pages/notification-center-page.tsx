"use client";

import { RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import { Alert } from "@/components/feedback/alert";
import { EmptyState } from "@/components/feedback/empty-state";
import { PageHeader } from "@/components/navigation/page-header";
import { Tabs } from "@/components/navigation/tabs";
import { buttonVariants } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { EMPTY_NOTIFICATION_FILTERS, NotificationFilters, type NotificationFilterValues } from "@/features/notifications/components/notification-filters";
import { NotificationList } from "@/features/notifications/components/notification-list";
import { useNotifications } from "@/features/notifications/hooks/use-notifications";
import { isImportant } from "@/features/notifications/lib/format";
import { NOTIFICATION_QUICK_VIEWS, type Notification, type NotificationCategoryValue, type NotificationQuickView, type NotificationSearchParams, type NotificationStatusValue } from "@/features/notifications/types";
import { useSession } from "@/auth/session";
import { formatRelativeTime } from "@/lib/relative-time";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

const PAGE_SIZE = 25;

const QUICK_VIEW_LABELS: Record<NotificationQuickView, string> = { all: "All", unread: "Unread", important: "Important" };

function applyQuickView(items: Notification[], view: NotificationQuickView): Notification[] {
  if (view === "unread") return items.filter((item) => item.readAt === null);
  if (view === "important") return items.filter((item) => isImportant(item.priority));
  return items;
}

function hasActiveFilters(filters: NotificationFilterValues): boolean {
  return Boolean(filters.category || filters.status);
}

/**
 * Notification Center — `/notifications` (§7). "Unread"/"Important"
 * (§4) are client-side quick views over the same real, already-fetched
 * page (never a second fetch — mirrors Prompt 015's Table/Timeline
 * rule) — see `NOTIFICATION_QUICK_VIEWS`' own docstring for why no
 * clean single server-side "unread" filter exists.
 */
export function NotificationCenterPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { userId } = useSession();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } = useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();

  const view = (searchParams.get("view") as NotificationQuickView | null) ?? "all";
  const offset = Number(searchParams.get("offset") ?? "0") || 0;
  const filters: NotificationFilterValues = useMemo(
    () => ({
      category: searchParams.get("category") ?? EMPTY_NOTIFICATION_FILTERS.category,
      status: searchParams.get("status") ?? EMPTY_NOTIFICATION_FILTERS.status,
    }),
    [searchParams],
  );

  const updateParams = useCallback(
    (next: Partial<{ view: string; category: string; status: string; offset: string }>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(next)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      router.push(`/notifications?${params.toString()}`);
    },
    [router, searchParams],
  );

  function handleViewChange(nextView: string) {
    updateParams({ view: nextView === "all" ? "" : nextView, offset: "" });
  }

  function handleFiltersChange(next: NotificationFilterValues) {
    updateParams({ category: next.category, status: next.status, offset: "" });
  }

  function handleReset() {
    updateParams({ category: "", status: "", offset: "" });
  }

  const searchQueryParams: NotificationSearchParams | null =
    selectedOrganizationId && userId
      ? {
          organizationId: selectedOrganizationId,
          userId,
          category: (filters.category as NotificationCategoryValue) || undefined,
          status: (filters.status as NotificationStatusValue) || undefined,
          limit: PAGE_SIZE,
          offset,
        }
      : null;

  const query = useNotifications(searchQueryParams);
  const visibleItems = query.data ? applyQuickView(query.data.items, view) : [];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Notifications"
        description="Notifications addressed to you across AI-IOS."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <div className="flex items-center gap-2">
            <Link href="/settings/notifications" className={buttonVariants("outline")}>
              Preferences
            </Link>
            <IconButton icon={RefreshCw} aria-label="Refresh notifications" variant="outline" loading={isRefreshing} onClick={refresh} />
          </div>
        }
      />

      <Alert tone="danger" title="This service checks no identity for reading or changing notifications">
        Listing, viewing, marking read, and acknowledging a notification all require no authentication at all — confirmed
        absent, not merely unenforced. The organization and user shown here are only what this session believes they are,
        never verified by the backend. This page&apos;s own visibility is a convenience, not a security boundary.
      </Alert>

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-4">
            <Tabs items={NOTIFICATION_QUICK_VIEWS.map((value) => ({ id: value, label: QUICK_VIEW_LABELS[value] }))} activeId={view} onChange={handleViewChange}>
              <div className="flex flex-col gap-4">
                <NotificationFilters values={filters} onChange={handleFiltersChange} onReset={handleReset} />

                <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-96 w-full">
                  {query.data &&
                    (visibleItems.length === 0 ? (
                      <EmptyState
                        title={view === "unread" ? "No unread notifications" : hasActiveFilters(filters) ? "No matching notifications" : "You're all caught up"}
                        description={
                          view === "unread"
                            ? "Nothing unread on this page."
                            : hasActiveFilters(filters)
                              ? "Try different filters."
                              : "No notifications found."
                        }
                      />
                    ) : (
                      <NotificationList result={query.data} items={visibleItems} onPageChange={(nextOffset) => updateParams({ offset: String(nextOffset) })} />
                    ))}
                </SectionState>
              </div>
            </Tabs>
          </div>
        )}
      </SectionState>
    </div>
  );
}
