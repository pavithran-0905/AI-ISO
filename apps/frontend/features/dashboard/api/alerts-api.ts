/**
 * `services/alerting-service/app/api/alerts.py` — confirmed by source
 * inspection, `GET /alerts` requires `organization_id`.
 */

import { apiClient } from "@/api/client";
import type { Alert, AlertSeverity, AlertStatusValue } from "@/features/dashboard/types";

interface AlertResponseBody {
  id: string;
  organization_id: string;
  severity: AlertSeverity;
  status: AlertStatusValue;
  title: string;
  message: string;
  source: string;
  triggered_at: string;
  resolved_at: string | null;
}

function toAlert(body: AlertResponseBody): Alert {
  return {
    id: body.id,
    organizationId: body.organization_id,
    severity: body.severity,
    status: body.status,
    title: body.title,
    message: body.message,
    source: body.source,
    triggeredAt: body.triggered_at,
    resolvedAt: body.resolved_at,
  };
}

export const alertsApi = {
  /** No `status`/`severity` filter — this dashboard determines "needs
   * attention" itself from the full set (`@/features/dashboard/types`'s
   * `RESOLVED_ALERT_STATUSES`) rather than issuing one request per
   * status value the backend happens to define. */
  async list(organizationId: string): Promise<Alert[]> {
    const body = await apiClient.get<AlertResponseBody[]>(
      `/alerts?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return body.map(toAlert);
  },
};
