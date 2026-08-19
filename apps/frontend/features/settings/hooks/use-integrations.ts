import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { integrationsApi } from "@/features/settings/api/integrations-api";
import type { AssignCredentialInput, ConfigureConnectorInput, CreateConnectorInput } from "@/features/settings/types";

export function useConnectors(organizationId: string | null) {
  return useQuery({
    queryKey: ["settings", "integrations", organizationId],
    queryFn: () => integrationsApi.list(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 30_000,
  });
}

export function useConnector(connectorId: string | null) {
  return useQuery({
    queryKey: ["settings", "integrations", "connector", connectorId],
    queryFn: () => integrationsApi.getById(connectorId as string),
    enabled: connectorId !== null,
    staleTime: 15_000,
  });
}

export function useCreateConnector() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateConnectorInput) => integrationsApi.create(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "integrations"] }),
  });
}

export function useConfigureConnector(connectorId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ConfigureConnectorInput) => integrationsApi.configure(connectorId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "integrations", "connector", connectorId] });
      queryClient.invalidateQueries({ queryKey: ["settings", "integrations"] });
    },
  });
}

export function useRemoveConnector() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (connectorId: string) => integrationsApi.remove(connectorId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "integrations"] }),
  });
}

export function useTestConnection(connectorId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => integrationsApi.testConnection(connectorId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "integrations", "connector", connectorId] });
      queryClient.invalidateQueries({ queryKey: ["settings", "integrations"] });
    },
  });
}

export function useSetConnectorEnabled(connectorId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => (enabled ? integrationsApi.enable(connectorId) : integrationsApi.disable(connectorId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "integrations", "connector", connectorId] });
      queryClient.invalidateQueries({ queryKey: ["settings", "integrations"] });
    },
  });
}

export function useAssignCredential(connectorId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AssignCredentialInput) => integrationsApi.assignCredential(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "integrations", "connector", connectorId] }),
  });
}

export function useRotateCredential(connectorId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ credentialId, rawValue }: { credentialId: string; rawValue: string }) =>
      integrationsApi.rotateCredential(credentialId, { rawValue }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "integrations", "connector", connectorId] }),
  });
}
