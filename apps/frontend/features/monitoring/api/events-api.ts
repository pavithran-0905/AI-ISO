/**
 * `services/observability-platform-service/app/api/observability.py` —
 * `GET /observability/events`. Organization-resolved server-side, same
 * as `services-api.ts` — see its module docstring.
 */

import { apiClient } from "@/api/client";
import type { EventKindValue, EventSeverityValue, ObservabilityEvent } from "@/features/monitoring/types";

interface ObservabilityEventResponseBody {
  id: string;
  event_kind: EventKindValue;
  severity: EventSeverityValue;
  title: string;
  occurred_at: string;
  ended_at: string | null;
  service_name: string | null;
}

interface EventsResponseBody {
  events: ObservabilityEventResponseBody[];
  page: { next_cursor: string | null; has_more: boolean };
}

function toObservabilityEvent(body: ObservabilityEventResponseBody): ObservabilityEvent {
  return {
    id: body.id,
    eventKind: body.event_kind,
    severity: body.severity,
    title: body.title,
    occurredAt: body.occurred_at,
    endedAt: body.ended_at,
    serviceName: body.service_name,
  };
}

export const eventsApi = {
  async list(pageSize = 50): Promise<ObservabilityEvent[]> {
    const body = await apiClient.get<EventsResponseBody>(`/observability/events?page_size=${pageSize}`);
    return body.events.map(toObservabilityEvent);
  },
};
