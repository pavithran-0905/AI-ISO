"use client";

import { useEffect, useRef } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { Skeleton } from "@/components/feedback/skeleton";
import { MessageItem } from "@/features/ai-assistant/components/message-item";
import { ToolCallList } from "@/features/ai-assistant/components/tool-call-list";
import { useMessages } from "@/features/ai-assistant/hooks/use-chat";
import { Bot } from "lucide-react";

/** The transcript panel. Messages come back already ordered by
 * `sequence` (`chatApi.listMessages`'s own guarantee) — no client-side
 * sort needed. */
export function MessageThread({ organizationId, conversationId }: { organizationId: string; conversationId: string }) {
  const messagesQuery = useMessages(conversationId);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messagesQuery.data?.length]);

  if (messagesQuery.isLoading) {
    return (
      <div className="flex flex-col gap-3 p-4" role="status" aria-label="Loading messages">
        <Skeleton className="h-12 w-2/3" />
        <Skeleton className="ml-auto h-8 w-1/2" />
        <Skeleton className="h-16 w-3/4" />
      </div>
    );
  }

  if (messagesQuery.isError) {
    return <p className="text-danger p-4 text-sm">This conversation could not be loaded.</p>;
  }

  if (!messagesQuery.data || messagesQuery.data.length === 0) {
    return <EmptyState icon={Bot} title="No messages yet" description="Send a message below to start." className="h-full" />;
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
      {messagesQuery.data.map((message) => (
        <MessageItem key={message.id} organizationId={organizationId} message={message} />
      ))}
      <ToolCallList organizationId={organizationId} conversationId={conversationId} />
      <div ref={bottomRef} />
    </div>
  );
}
