"use client";

import { RefreshCw } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { Alert } from "@/components/feedback/alert";
import { EmptyState } from "@/components/feedback/empty-state";
import { PageHeader } from "@/components/navigation/page-header";
import { Tabs } from "@/components/navigation/tabs";
import { IconButton } from "@/components/ui/icon-button";
import { AuditSubNav } from "@/features/audit/components/audit-sub-nav";
import { EMPTY_AUDIT_FILTERS, AuditFilters, type AuditFilterValues } from "@/features/audit/components/audit-filters";
import { AuditEventTable } from "@/features/audit/components/audit-event-table";
import { AuditEventTimeline } from "@/features/audit/components/audit-event-timeline";
import { AuditViewToggle, type AuditViewMode } from "@/features/audit/components/audit-view-toggle";
import { EventDetailDrawer } from "@/features/audit/components/event-detail-drawer";
import { ExportAuditControl } from "@/features/audit/components/export-audit-control";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useAuditEvents } from "@/features/audit/hooks/use-audit";
import { AUDIT_SOURCES, AUDIT_SOURCE_LABELS, type AuditEvent, type AuditEventSearchParams, type AuditSourceValue } from "@/features/audit/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { useRefreshAction } from "@/lib/use-refresh-action";
import { useSelectedOrganization } from "@/organization/use-organizations";

const PAGE_SIZE = 25;

const SOURCE_AUTH_NOTES: Record<AuditSourceValue, string> = {
  compliance: "This route only requires a valid session token — no role or permission is checked.",
  integrations: "This route requires no authentication at all — confirmed absent, not merely unenforced.",
  notifications: "This route requires no authentication at all — confirmed absent, not merely unenforced.",
};

function hasActiveFilters(filters: AuditFilterValues): boolean {
  return Boolean(filters.entityType || filters.entityId || filters.actorId || filters.action || filters.days);
}

/**
 * Activity / Audit Events — `/audit/activity` (§7, §21, §22). One
 * source at a time; switching sources resets filters and paging, since
 * each source's filter set and result set are genuinely different
 * (never a shared "page N" across sources). Event Detail is a drawer
 * (§8), not a route — see `EventDetailDrawer`'s own docstring.
 */
export function AuditActivityPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { refresh, isRefreshing, lastRefreshedAt } = useRefreshAction();
  const [viewMode, setViewMode] = useState<AuditViewMode>("table");
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);

  const source = (searchParams.get("source") as AuditSourceValue | null) ?? "compliance";
  const offset = Number(searchParams.get("offset") ?? "0") || 0;
  const filters: AuditFilterValues = useMemo(
    () => ({
      entityType: searchParams.get("entityType") ?? EMPTY_AUDIT_FILTERS.entityType,
      entityId: searchParams.get("entityId") ?? EMPTY_AUDIT_FILTERS.entityId,
      actorId: searchParams.get("actorId") ?? EMPTY_AUDIT_FILTERS.actorId,
      action: searchParams.get("action") ?? EMPTY_AUDIT_FILTERS.action,
      days: searchParams.get("days") ?? EMPTY_AUDIT_FILTERS.days,
    }),
    [searchParams],
  );

  const updateParams = useCallback(
    (next: Partial<{ source: string; entityType: string; entityId: string; actorId: string; action: string; days: string; offset: string }>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(next)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      router.push(`/audit/activity?${params.toString()}`);
    },
    [router, searchParams],
  );

  function handleSourceChange(nextSource: string) {
    updateParams({ source: nextSource, entityType: "", entityId: "", actorId: "", action: "", days: "", offset: "" });
  }

  function handleFiltersChange(next: AuditFilterValues) {
    updateParams({ entityType: next.entityType, entityId: next.entityId, actorId: next.actorId, action: next.action, days: next.days, offset: "" });
  }

  function handleReset() {
    updateParams({ entityType: "", entityId: "", actorId: "", action: "", days: "", offset: "" });
  }

  const searchQueryParams: AuditEventSearchParams | null = selectedOrganizationId
    ? {
        organizationId: selectedOrganizationId,
        entityType: filters.entityType || undefined,
        entityId: filters.entityId || undefined,
        actorId: filters.actorId || undefined,
        action: filters.action || undefined,
        days: filters.days ? Number(filters.days) : undefined,
        limit: PAGE_SIZE,
        offset,
      }
    : null;

  const query = useAuditEvents(source, searchQueryParams);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Activity"
        description="Searchable, filterable audit events, one source at a time."
        secondaryActions={
          <span className="text-muted-foreground hidden text-xs sm:inline">
            Updated <time dateTime={lastRefreshedAt}>{formatRelativeTime(lastRefreshedAt)}</time>
          </span>
        }
        primaryAction={
          <IconButton icon={RefreshCw} aria-label="Refresh audit data" variant="outline" loading={isRefreshing} onClick={refresh} />
        }
      />
      <AuditSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-4">
            <Tabs
              items={AUDIT_SOURCES.map((value) => ({ id: value, label: AUDIT_SOURCE_LABELS[value] }))}
              activeId={source}
              onChange={handleSourceChange}
            >
              <div className="flex flex-col gap-4">
                <Alert tone="danger" title="This source's audit route has no access control of its own">
                  {SOURCE_AUTH_NOTES[source]} This page&apos;s own nav gating is a UX convenience, not a security
                  boundary — the backend remains the sole authority.
                </Alert>

                <div className="flex flex-wrap items-center justify-between gap-3">
                  <AuditFilters source={source} values={filters} onChange={handleFiltersChange} onReset={handleReset} />
                  <AuditViewToggle value={viewMode} onChange={setViewMode} />
                </div>

                {source === "compliance" && <ExportAuditControl organizationId={selectedOrganizationId} />}

                <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-96 w-full">
                  {query.data &&
                    (query.data.items.length === 0 ? (
                      <EmptyState
                        title={hasActiveFilters(filters) ? "No matching events" : "No events found"}
                        description={hasActiveFilters(filters) ? "Try different filters." : "No audit events have been recorded for this source yet."}
                      />
                    ) : viewMode === "table" ? (
                      <AuditEventTable result={query.data} onPageChange={(nextOffset) => updateParams({ offset: String(nextOffset) })} onSelectEvent={setSelectedEvent} />
                    ) : (
                      <AuditEventTimeline result={query.data} />
                    ))}
                </SectionState>
              </div>
            </Tabs>
          </div>
        )}
      </SectionState>

      <EventDetailDrawer event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
