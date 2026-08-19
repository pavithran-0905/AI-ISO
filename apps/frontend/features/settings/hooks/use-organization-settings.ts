import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { organizationApi } from "@/features/settings/api/organization-api";
import type {
  UpdateOrganizationBrandingInput,
  UpdateOrganizationIdentityInput,
  UpdateOrganizationSettingsInput,
} from "@/features/settings/types";

export function useOrganizationIdentity(organizationId: string | null) {
  return useQuery({
    queryKey: ["settings", "organization", organizationId, "identity"],
    queryFn: () => organizationApi.getIdentity(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function useUpdateOrganizationIdentity(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateOrganizationIdentityInput) => organizationApi.updateIdentity(organizationId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "organization", organizationId, "identity"] }),
  });
}

export function useOrganizationSettings(organizationId: string | null) {
  return useQuery({
    queryKey: ["settings", "organization", organizationId, "settings"],
    queryFn: () => organizationApi.getSettings(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function useUpdateOrganizationSettings(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateOrganizationSettingsInput) => organizationApi.updateSettings(organizationId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "organization", organizationId, "settings"] }),
  });
}

export function useOrganizationBranding(organizationId: string | null) {
  return useQuery({
    queryKey: ["settings", "organization", organizationId, "branding"],
    queryFn: () => organizationApi.getBranding(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function useUpdateOrganizationBranding(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateOrganizationBrandingInput) => organizationApi.updateBranding(organizationId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings", "organization", organizationId, "branding"] }),
  });
}

export function useOrganizationLicense(organizationId: string | null) {
  return useQuery({
    queryKey: ["settings", "organization", organizationId, "license"],
    queryFn: () => organizationApi.getLicense(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}

export function useOrganizationQuota(organizationId: string | null) {
  return useQuery({
    queryKey: ["settings", "organization", organizationId, "quota"],
    queryFn: () => organizationApi.getQuota(organizationId as string),
    enabled: organizationId !== null,
    staleTime: 60_000,
  });
}
