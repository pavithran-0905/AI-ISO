"use client";

import Link from "next/link";
import { useMemo } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { Skeleton } from "@/components/feedback/skeleton";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { useConversations } from "@/features/ai-assistant/hooks/use-chat";
import { CONVERSATION_STATUS_TO_STATUS } from "@/features/ai-assistant/lib/status-maps";
import { formatRelativeTime } from "@/lib/relative-time";
import { MessageSquare } from "lucide-react";

const RECENT_LIMIT = 5;

/** The overview's compact preview — this user's own most recent
 * conversations, sorted client-side by `startedAt` (the list endpoint
 * makes no ordering guarantee of its own). */
export function RecentConversationsList({ organizationId }: { organizationId: string }) {
  const conversationsQuery = useConversations(organizationId, true);

  const recent = useMemo(() => {
    if (!conversationsQuery.data) return [];
    return [...conversationsQuery.data]
      .sort((a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime())
      .slice(0, RECENT_LIMIT);
  }, [conversationsQuery.data]);

  if (conversationsQuery.isLoading) {
    return (
      <div className="flex flex-col gap-2" role="status" aria-label="Loading recent conversations">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  if (recent.length === 0) {
    return <EmptyState icon={MessageSquare} title="No conversations yet" description="Ask the assistant something to get started." />;
  }

  return (
    <ul className="flex flex-col gap-1">
      {recent.map((conversation) => (
        <li key={conversation.id}>
          <Link
            href={`/intelligence/assistant?conversation=${encodeURIComponent(conversation.id)}`}
            className="hover:bg-muted focus-visible:ring-ring flex items-center justify-between gap-2 rounded-md p-2 text-sm focus-visible:ring-2 focus-visible:outline-none"
          >
            <span className="truncate">{conversation.title || "Untitled conversation"}</span>
            <span className="text-muted-foreground flex shrink-0 items-center gap-2 text-xs">
              <StatusIndicator state={CONVERSATION_STATUS_TO_STATUS[conversation.status]} />
              {formatRelativeTime(conversation.startedAt)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
