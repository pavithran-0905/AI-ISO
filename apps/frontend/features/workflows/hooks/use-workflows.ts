import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { workflowsApi } from "@/features/workflows/api/workflows-api";
import {
  ACTIVE_INSTANCE_STATUSES,
  type ApprovalDecisionInput,
  type WorkflowInstance,
  type WorkflowInstanceStatusValue,
} from "@/features/workflows/types";

/** `workflow-runtime-service` exposes no WebSocket or SSE endpoint
 * either (confirmed by source inspection), so following a running
 * instance means polling. */
const ACTIVE_POLL_MS = 5_000;

export function useWorkflows(organizationId: string | null) {
  return useQuery({
    queryKey: ["workflows", "definitions", organizationId],
    queryFn: () => workflowsApi.list(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useWorkflow(workflowId: string | null) {
  return useQuery({
    queryKey: ["workflows", "definitions", workflowId],
    queryFn: () => workflowsApi.getById(workflowId as string),
    enabled: workflowId !== null,
    staleTime: 15_000,
  });
}

export function useWorkflowInstances(organizationId: string | null, status?: WorkflowInstanceStatusValue) {
  return useQuery({
    queryKey: ["workflows", "instances", organizationId, status],
    queryFn: () => workflowsApi.listInstances(organizationId as string, status),
    enabled: organizationId !== null,
    staleTime: 15_000,
    refetchInterval: 15_000,
  });
}

/** Stops polling once the instance reaches a terminal state. */
export function useWorkflowInstance(instanceId: string | null) {
  return useQuery({
    queryKey: ["workflows", "instances", instanceId],
    queryFn: () => workflowsApi.getInstance(instanceId as string),
    enabled: instanceId !== null,
    staleTime: 0,
    refetchInterval: (query) => {
      const instance = query.state.data as WorkflowInstance | undefined;
      if (!instance) return false;
      return ACTIVE_INSTANCE_STATUSES.has(instance.status) ? ACTIVE_POLL_MS : false;
    },
  });
}

export function useInstanceSteps(instanceId: string | null, isActive: boolean) {
  return useQuery({
    queryKey: ["workflows", "instances", instanceId, "steps"],
    queryFn: () => workflowsApi.listInstanceSteps(instanceId as string),
    enabled: instanceId !== null,
    staleTime: 0,
    refetchInterval: isActive ? ACTIVE_POLL_MS : false,
  });
}

export function useInstanceLogs(instanceId: string | null, isActive: boolean) {
  return useQuery({
    queryKey: ["workflows", "instances", instanceId, "logs"],
    queryFn: () => workflowsApi.listInstanceLogs(instanceId as string),
    enabled: instanceId !== null,
    staleTime: 0,
    refetchInterval: isActive ? ACTIVE_POLL_MS : false,
  });
}

export function useInstanceApprovals(instanceId: string | null, isActive: boolean) {
  return useQuery({
    queryKey: ["workflows", "instances", instanceId, "approvals"],
    queryFn: () => workflowsApi.listInstanceApprovals(instanceId as string),
    enabled: instanceId !== null,
    staleTime: 0,
    refetchInterval: isActive ? ACTIVE_POLL_MS : false,
  });
}

/** Like automation, every workflow mutation waits for the backend's
 * confirmed response — these start and stop real infrastructure work. */
export function useExecuteWorkflow(workflowId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (variables: Record<string, unknown>) => workflowsApi.execute(workflowId, variables),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows", "instances"] });
    },
  });
}

export function usePauseWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (workflowId: string) => workflowsApi.pause(workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows", "instances"] });
    },
  });
}

export function useResumeWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (workflowId: string) => workflowsApi.resume(workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows", "instances"] });
    },
  });
}

export function useCancelWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (workflowId: string) => workflowsApi.cancel(workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows", "instances"] });
    },
  });
}

export function useDecideApproval(instanceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ approvalId, input }: { approvalId: string; input: ApprovalDecisionInput }) =>
      workflowsApi.decideApproval(instanceId, approvalId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows", "instances", instanceId] });
    },
  });
}
