/**
 * `services/alerting-service/app/api/maintenance_windows.py` —
 * `GET /maintenance-windows`. Read-only in this feature — creating a
 * window isn't exposed as UI yet (the `POST` endpoint exists but no
 * creation form was built this prompt, per keeping scope to what §14
 * asks: "represent them clearly," not full CRUD management).
 */

import { apiClient } from "@/api/client";
import type { MaintenanceWindow } from "@/features/alerting/types";

interface MaintenanceWindowResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  name: string;
  window_type: string;
  scope: string;
  scope_reference: string | null;
  starts_at: string;
  ends_at: string;
  enabled: boolean;
}

export const maintenanceWindowsApi = {
  async list(organizationId: string, activeOnly = false): Promise<MaintenanceWindow[]> {
    const query = new URLSearchParams({ organization_id: organizationId, active_only: String(activeOnly) });
    const body = await apiClient.get<MaintenanceWindowResponseBody[]>(`/maintenance-windows?${query.toString()}`);
    return body.map((window) => ({
      id: window.id,
      organizationId: window.organization_id,
      projectId: window.project_id,
      name: window.name,
      windowType: window.window_type,
      scope: window.scope,
      scopeReference: window.scope_reference,
      startsAt: window.starts_at,
      endsAt: window.ends_at,
      enabled: window.enabled,
    }));
  },
};
