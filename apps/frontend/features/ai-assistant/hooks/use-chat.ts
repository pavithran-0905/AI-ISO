import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { chatApi } from "@/features/ai-assistant/api/chat-api";
import type { SendMessageInput } from "@/features/ai-assistant/types";

export function useConversations(organizationId: string | null, mineOnly: boolean) {
  return useQuery({
    queryKey: ["ai-assistant", "conversations", organizationId, mineOnly],
    queryFn: () => chatApi.listConversations(organizationId as string, mineOnly),
    enabled: organizationId !== null,
    staleTime: 15_000,
  });
}

export function useConversation(conversationId: string | null) {
  return useQuery({
    queryKey: ["ai-assistant", "conversations", conversationId],
    queryFn: () => chatApi.getConversation(conversationId as string),
    enabled: conversationId !== null,
    staleTime: 15_000,
  });
}

export function useMessages(conversationId: string | null) {
  return useQuery({
    queryKey: ["ai-assistant", "conversations", conversationId, "messages"],
    queryFn: () => chatApi.listMessages(conversationId as string),
    enabled: conversationId !== null,
    staleTime: 5_000,
  });
}

export function useToolCalls(conversationId: string | null) {
  return useQuery({
    queryKey: ["ai-assistant", "conversations", conversationId, "tool-calls"],
    queryFn: () => chatApi.listToolCalls(conversationId as string),
    enabled: conversationId !== null,
    staleTime: 5_000,
  });
}

/** A send is a single synchronous round-trip — there is no
 * "generating" placeholder to insert optimistically (see `chat-api.ts`
 * for why streaming isn't consumed). Invalidating the whole
 * `["ai-assistant", "conversations"]` prefix covers the conversation
 * list, the sent-to conversation's messages, and its tool calls in one
 * call — a send with no `conversationId` also creates a brand new
 * conversation the list doesn't know about yet. */
export function useSendMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: SendMessageInput) => chatApi.send(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-assistant", "conversations"] });
    },
  });
}
