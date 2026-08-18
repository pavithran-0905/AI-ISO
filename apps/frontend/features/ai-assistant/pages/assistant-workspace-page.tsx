"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { AiAssistantSubNav } from "@/features/ai-assistant/components/ai-assistant-sub-nav";
import { Composer } from "@/features/ai-assistant/components/composer";
import { ConversationList } from "@/features/ai-assistant/components/conversation-list";
import { MessageThread } from "@/features/ai-assistant/components/message-thread";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useSelectedOrganization } from "@/organization/use-organizations";

/**
 * `/intelligence/assistant` — the two-panel workspace §5 recommends: a
 * conversation list on the left, the active conversation's transcript
 * and composer on the right. Sending the first message of a brand new
 * conversation reveals its real id only once the backend's synchronous
 * response arrives (see `chat-api.ts`) — there is no client-generated
 * conversation id to select ahead of that.
 *
 * `?conversation=<id>` and `?draft=<text>` make this page a real link
 * target: the former lets `RecentConversationsList` and the command
 * palette open a specific conversation directly; the latter is what
 * every cross-module "Ask AI" entry point (§41) uses to pre-fill the
 * composer with a real entity reference — never auto-sent, since
 * nothing should leave this page without the user pressing Send.
 */
export function AssistantWorkspacePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(searchParams.get("conversation"));
  const initialDraft = searchParams.get("draft") ?? "";

  const selectConversation = useCallback(
    (conversationId: string | null) => {
      setSelectedConversationId(conversationId);
      const params = new URLSearchParams();
      if (conversationId) params.set("conversation", conversationId);
      router.replace(params.size > 0 ? `/intelligence/assistant?${params.toString()}` : "/intelligence/assistant");
    },
    [router],
  );

  return (
    <div className="flex h-full flex-col gap-6">
      <PageHeader title="AI Assistant" description="Ask questions grounded in retrieved platform knowledge." />
      <AiAssistantSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-[18rem_1fr]">
            <div className="border-border md:border-r md:pr-4">
              <ConversationList
                organizationId={selectedOrganizationId}
                selectedConversationId={selectedConversationId}
                onSelect={selectConversation}
                onNewConversation={() => selectConversation(null)}
              />
            </div>

            <div className="border-border flex min-h-[28rem] flex-col rounded-lg border">
              {selectedConversationId === null ? (
                <div className="text-muted-foreground flex flex-1 items-center justify-center p-4 text-center text-sm">
                  Send a message below to start a new conversation.
                </div>
              ) : (
                <MessageThread organizationId={selectedOrganizationId} conversationId={selectedConversationId} />
              )}
              <Composer
                organizationId={selectedOrganizationId}
                conversationId={selectedConversationId}
                initialDraft={selectedConversationId === null ? initialDraft : ""}
                onSent={(result) => selectConversation(result.conversationId)}
              />
            </div>
          </div>
        )}
      </SectionState>
    </div>
  );
}
