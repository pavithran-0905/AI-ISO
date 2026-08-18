import { useQuery } from "@tanstack/react-query";

import { executionsApi, type ExecutionListParams } from "@/features/automation/api/executions-api";
import { ACTIVE_EXECUTION_STATUSES, type AutomationExecution } from "@/features/automation/types";

/** How often an in-flight execution is re-polled. `automation-service`
 * exposes no WebSocket or SSE endpoint (confirmed by source
 * inspection), so polling is the only way to follow a run — §18's
 * "if only polling exists, use existing polling behaviour". */
const ACTIVE_POLL_MS = 5_000;

export function useExecutions(params: ExecutionListParams | null) {
  return useQuery({
    queryKey: ["automation", "executions", params],
    queryFn: () => executionsApi.list(params as ExecutionListParams),
    enabled: params !== null,
    staleTime: 15_000,
    refetchInterval: 15_000,
  });
}

/** Polls only while the execution is genuinely still in flight, then
 * stops — a terminal execution never changes again, so continuing to
 * poll it would be pure waste. */
export function useExecution(executionId: string | null) {
  return useQuery({
    queryKey: ["automation", "executions", executionId],
    queryFn: () => executionsApi.getById(executionId as string),
    enabled: executionId !== null,
    staleTime: 0,
    refetchInterval: (query) => {
      const execution = query.state.data as AutomationExecution | undefined;
      if (!execution) return false;
      return ACTIVE_EXECUTION_STATUSES.has(execution.status) ? ACTIVE_POLL_MS : false;
    },
  });
}

/** Log polling follows the same rule as the execution itself: keep
 * fetching while the run is active (new step output appears as it
 * goes), stop once it's terminal. */
export function useExecutionLogs(executionId: string | null, isActive: boolean) {
  return useQuery({
    queryKey: ["automation", "executions", executionId, "logs"],
    queryFn: () => executionsApi.listLogs(executionId as string),
    enabled: executionId !== null,
    staleTime: 0,
    refetchInterval: isActive ? ACTIVE_POLL_MS : false,
  });
}
