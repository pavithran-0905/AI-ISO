import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { rbacApi } from "@/features/administration/api/rbac-api";
import type { AssignRoleInput } from "@/features/administration/types";

export function useRbacRoles() {
  return useQuery({ queryKey: ["administration", "rbac", "roles"], queryFn: rbacApi.listRoles, staleTime: 5 * 60_000 });
}

export function useRbacRole(roleId: string | null) {
  return useQuery({
    queryKey: ["administration", "rbac", "roles", roleId],
    queryFn: () => rbacApi.getRole(roleId as string),
    enabled: roleId !== null,
    staleTime: 5 * 60_000,
  });
}

export function useRbacPermissions() {
  return useQuery({ queryKey: ["administration", "rbac", "permissions"], queryFn: rbacApi.listPermissions, staleTime: 5 * 60_000 });
}

export function useAssignRole(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AssignRoleInput) => rbacApi.assignRole(userId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["administration", "rbac"] }),
  });
}
