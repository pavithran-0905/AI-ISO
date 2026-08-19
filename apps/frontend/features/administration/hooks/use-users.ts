import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { usersApi } from "@/features/administration/api/users-api";
import type { PatchUserInput, UserSearchParams } from "@/features/administration/types";

export function useUserSearch(params: UserSearchParams) {
  return useQuery({
    queryKey: ["administration", "users", "search", params],
    queryFn: () => usersApi.search(params),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
}

export function useUser(userId: string | null) {
  return useQuery({
    queryKey: ["administration", "users", userId],
    queryFn: () => usersApi.getById(userId as string),
    enabled: userId !== null,
    staleTime: 15_000,
  });
}

export function usePatchUser(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PatchUserInput) => usersApi.patch(userId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["administration", "users"] });
    },
  });
}

export function useRemoveUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => usersApi.remove(userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["administration", "users"] }),
  });
}

export function useUserNotes(userId: string | null) {
  return useQuery({
    queryKey: ["administration", "users", userId, "notes"],
    queryFn: () => usersApi.listNotes(userId as string),
    enabled: userId !== null,
    staleTime: 15_000,
  });
}

export function useAddUserNote(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => usersApi.addNote(userId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["administration", "users", userId, "notes"] }),
  });
}

export function useRemoveUserNote(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (noteId: string) => usersApi.removeNote(userId, noteId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["administration", "users", userId, "notes"] }),
  });
}
