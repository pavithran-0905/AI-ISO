import { useQuery } from "@tanstack/react-query";

import { maintenanceWindowsApi } from "@/features/alerting/api/maintenance-windows-api";

export function useMaintenanceWindows(organizationId: string | null, activeOnly = true) {
  return useQuery({
    queryKey: ["maintenance-windows", organizationId, activeOnly],
    queryFn: () => maintenanceWindowsApi.list(organizationId as string, activeOnly),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}
