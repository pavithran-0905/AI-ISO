import { useQuery } from "@tanstack/react-query";

import { eventsApi } from "@/features/monitoring/api/events-api";

export function useObservabilityEvents() {
  return useQuery({
    queryKey: ["monitoring", "events"],
    queryFn: () => eventsApi.list(),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}
