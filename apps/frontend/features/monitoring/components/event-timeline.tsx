"use client";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useObservabilityEvents } from "@/features/monitoring/hooks/use-observability-events";
import { EVENT_SEVERITY_TONE } from "@/features/monitoring/lib/status-maps";
import type { ObservabilityEvent } from "@/features/monitoring/types";
import { formatRelativeTime } from "@/lib/relative-time";

/**
 * Event Timeline (§13) — `GET /observability/events`, real chronological
 * ordering by `occurred_at`. No asset cross-reference exists on this
 * endpoint (only `service_name`), so events link nowhere yet — see
 * `docs/frontend/developer-guide/monitoring.md`.
 */
export function EventTimeline({ limit }: { limit?: number }) {
  const query = useObservabilityEvents();

  return (
    <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()} skeletonClassName="h-48 w-full">
      {query.data && <EventList events={query.data} limit={limit} />}
    </SectionState>
  );
}

function EventList({ events, limit }: { events: ObservabilityEvent[]; limit?: number }) {
  if (events.length === 0) {
    return <EmptyState title="No recent events" description="Nothing has been recorded in the selected window." />;
  }

  const sorted = [...events].sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime());
  const visible = limit ? sorted.slice(0, limit) : sorted;

  return (
    <ul className="flex flex-col gap-2">
      {visible.map((event) => (
        <li key={event.id}>
          <Card>
            <CardContent className="flex items-start justify-between gap-3 p-3">
              <div className="flex flex-col gap-0.5">
                <p className="text-sm font-medium">{event.title}</p>
                <p className="text-muted-foreground text-xs">
                  {event.eventKind}
                  {event.serviceName && ` · ${event.serviceName}`} ·{" "}
                  <time dateTime={event.occurredAt}>{formatRelativeTime(event.occurredAt)}</time>
                </p>
              </div>
              <StatusBadge tone={EVENT_SEVERITY_TONE[event.severity]} label={event.severity} className="shrink-0 uppercase" />
            </CardContent>
          </Card>
        </li>
      ))}
    </ul>
  );
}
