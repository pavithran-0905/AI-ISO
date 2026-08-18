import { useQuery } from "@tanstack/react-query";

import { servicesApi } from "@/features/monitoring/api/services-api";

export function useServiceTopology() {
  return useQuery({
    queryKey: ["monitoring", "topology"],
    queryFn: () => servicesApi.fetchTopology(),
    staleTime: 30_000,
  });
}
