"use client";

import { useState } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { AiAssistantSubNav } from "@/features/ai-assistant/components/ai-assistant-sub-nav";
import { PromptCreateForm } from "@/features/ai-assistant/components/prompt-create-form";
import { PromptDetail } from "@/features/ai-assistant/components/prompt-detail";
import { PromptList } from "@/features/ai-assistant/components/prompt-list";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { usePrompts } from "@/features/ai-assistant/hooks/use-prompts";
import { usePermissions } from "@/permissions/hooks";
import { useSelectedOrganization } from "@/organization/use-organizations";

/**
 * `/intelligence/prompts` — a modest, admin-gated view onto the
 * prompt templates the assistant's own agents draw on. See
 * `PromptDetail`'s own docstring for why the gating is UX-only.
 */
export function PromptsPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { isAdministrative } = usePermissions();
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null);
  const promptsQuery = usePrompts(selectedOrganizationId);
  const selectedPrompt = promptsQuery.data?.find((prompt) => prompt.id === selectedPromptId) ?? null;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Prompts" description="Prompt templates the assistant's own agents draw on: versioning, approval, and rollback." />
      <AiAssistantSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[20rem_1fr]">
            <div className="flex flex-col gap-4">
              <PromptList organizationId={selectedOrganizationId} selectedPromptId={selectedPromptId} onSelect={setSelectedPromptId} />
              {isAdministrative && <PromptCreateForm organizationId={selectedOrganizationId} onCreated={setSelectedPromptId} />}
            </div>

            <div>
              {selectedPrompt ? (
                <PromptDetail prompt={selectedPrompt} />
              ) : (
                <p className="text-muted-foreground text-sm">Select a prompt to view its versions.</p>
              )}
            </div>
          </div>
        )}
      </SectionState>
    </div>
  );
}
