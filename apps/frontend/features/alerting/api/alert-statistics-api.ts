/**
 * `services/alerting-service/app/api/alert_analytics.py` —
 * `GET /alert-statistics`.
 */

import { apiClient } from "@/api/client";
import type { AlertStatistics } from "@/features/alerting/types";

interface AlertStatisticsResponseBody {
  total_alerts: number;
  open_alert_count: number;
  noise_ratio: number;
  suppression_rate: number;
  average_resolution_seconds: number | null;
  mtta_seconds: number | null;
  mttr_seconds: number | null;
  computed_at: string;
}

export const alertStatisticsApi = {
  async fetch(organizationId: string): Promise<AlertStatistics> {
    const body = await apiClient.get<AlertStatisticsResponseBody>(
      `/alert-statistics?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return {
      totalAlerts: body.total_alerts,
      openAlertCount: body.open_alert_count,
      noiseRatio: body.noise_ratio,
      suppressionRate: body.suppression_rate,
      averageResolutionSeconds: body.average_resolution_seconds,
      mttaSeconds: body.mtta_seconds,
      mttrSeconds: body.mttr_seconds,
      computedAt: body.computed_at,
    };
  },
};
