"use client";

import Link from "next/link";

import { EmptyState } from "@/components/feedback/empty-state";
import { buttonVariants } from "@/components/ui/button";
import { ResourceSection } from "@/components/resource/resource-section";
import { useAuditEvents } from "@/features/audit/hooks/use-audit";
import { formatActionLabel } from "@/features/audit/lib/format";
import { formatRelativeTime } from "@/lib/relative-time";
import { cn } from "@/utils/cn";

const LIMIT = 8;

/**
 * §17's Activity Timeline. Only `compliance-service`'s own audit trail
 * (Prompt 015's primary/richest source) — showing all three real,
 * unrelated audit sources here would repeat Audit & Activity's own
 * source-selector rather than give a quick, single-glance recent feed.
 * Labeled plainly as compliance activity, never a cross-platform feed
 * (no such thing exists — see the developer guide).
 */
export function RecentActivityTimeline({ organizationId }: { organizationId: string }) {
  const query = useAuditEvents("compliance", { organizationId, days: 1, limit: LIMIT, offset: 0 });

  return (
    <ResourceSection
      title="Recent activity"
      action={
        <Link href="/audit/activity" className={cn(buttonVariants("ghost"), "text-xs")}>
          View full activity
        </Link>
      }
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
    >
      {query.data &&
        (query.data.items.length === 0 ? (
          <EmptyState title="No recent activity" description="No compliance activity in the last 24 hours." />
        ) : (
          <ol className="flex flex-col gap-3 border-l border-border pl-4">
            {query.data.items.map((event) => (
              <li key={event.id} className="relative">
                <span className="bg-primary absolute top-1.5 -left-[21px] size-2 rounded-full" aria-hidden="true" />
                <time dateTime={event.occurredAt} className="text-muted-foreground text-xs">
                  {formatRelativeTime(event.occurredAt)}
                </time>
                <p className="text-sm">{formatActionLabel(event.action)}</p>
                {event.entityReference && <p className="text-muted-foreground text-xs">{event.entityReference}</p>}
              </li>
            ))}
          </ol>
        ))}
    </ResourceSection>
  );
}
