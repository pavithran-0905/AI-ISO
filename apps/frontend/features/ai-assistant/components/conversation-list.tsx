"use client";

import { MessageSquarePlus } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { Skeleton } from "@/components/feedback/skeleton";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { Switch } from "@/components/forms/switch";
import { Button } from "@/components/ui/button";
import { useConversations } from "@/features/ai-assistant/hooks/use-chat";
import { CONVERSATION_STATUS_TO_STATUS } from "@/features/ai-assistant/lib/status-maps";
import { formatRelativeTime } from "@/lib/relative-time";
import { cn } from "@/utils/cn";

/**
 * The left panel of the two-panel workspace (§5). Defaults to
 * `mine_only=true` — a user's own conversations first, with an
 * explicit toggle to see the whole organization's, since nothing in
 * this V1 backend enforces conversation privacy either way (see
 * `docs/frontend/backend-v1-integration-limitations.md`).
 */
export function ConversationList({
  organizationId,
  selectedConversationId,
  onSelect,
  onNewConversation,
}: {
  organizationId: string;
  selectedConversationId: string | null;
  onSelect: (conversationId: string) => void;
  onNewConversation: () => void;
}) {
  const [mineOnly, setMineOnly] = useState(true);
  const conversationsQuery = useConversations(organizationId, mineOnly);

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <Button onClick={onNewConversation} className="flex-1 gap-1.5">
          <MessageSquarePlus className="size-4" aria-hidden="true" />
          New conversation
        </Button>
      </div>

      <label className="flex items-center justify-between gap-2 text-sm">
        <span className="text-muted-foreground">My conversations only</span>
        <Switch checked={mineOnly} onChange={(event) => setMineOnly(event.target.checked)} aria-label="My conversations only" />
      </label>

      <div className="flex-1 overflow-y-auto">
        {conversationsQuery.isLoading && (
          <div className="flex flex-col gap-2" role="status" aria-label="Loading conversations">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        )}

        {conversationsQuery.isError && (
          <p className="text-danger text-sm">Conversations could not be loaded.</p>
        )}

        {conversationsQuery.data && conversationsQuery.data.length === 0 && (
          <EmptyState
            icon={MessageSquarePlus}
            title="No conversations yet"
            description="Start a new conversation to ask the assistant something."
          />
        )}

        {conversationsQuery.data && conversationsQuery.data.length > 0 && (
          <ul className="flex flex-col gap-1">
            {conversationsQuery.data.map((conversation) => (
              <li key={conversation.id}>
                <button
                  type="button"
                  onClick={() => onSelect(conversation.id)}
                  aria-current={conversation.id === selectedConversationId ? "true" : undefined}
                  className={cn(
                    "flex w-full flex-col gap-1 rounded-md border p-2.5 text-left text-sm transition-colors",
                    "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
                    conversation.id === selectedConversationId
                      ? "border-primary bg-primary/5"
                      : "border-transparent hover:bg-muted",
                  )}
                >
                  <span className="truncate font-medium">{conversation.title || "Untitled conversation"}</span>
                  <span className="text-muted-foreground flex items-center justify-between gap-2 text-xs">
                    <StatusIndicator state={CONVERSATION_STATUS_TO_STATUS[conversation.status]} />
                    <time dateTime={conversation.startedAt}>{formatRelativeTime(conversation.startedAt)}</time>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
