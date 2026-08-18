"use client";

import { PageHeader } from "@/components/navigation/page-header";
import { AiAssistantSubNav } from "@/features/ai-assistant/components/ai-assistant-sub-nav";
import { AiStatisticsSummary } from "@/features/ai-assistant/components/ai-statistics-summary";
import { MemoryList } from "@/features/ai-assistant/components/memory-list";
import { PendingRecommendationsList } from "@/features/ai-assistant/components/pending-recommendations-list";
import { RecentConversationsList } from "@/features/ai-assistant/components/recent-conversations-list";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { typography } from "@/lib/typography";
import { useSelectedOrganization } from "@/organization/use-organizations";
import { cn } from "@/utils/cn";

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className={cn(typography.cardTitle, "mb-3")}>{children}</h2>;
}

/** `/intelligence` — mirrors Reporting's/Monitoring's/Alerting's own
 * overview structure (sub-nav + summary sections). */
export function IntelligenceOverviewPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Intelligence" description="AI-IOS operations copilot, grounded in retrieved platform documentation." />
      <AiAssistantSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-8">
            <section>
              <SectionHeading>Summary</SectionHeading>
              <AiStatisticsSummary organizationId={selectedOrganizationId} />
            </section>

            <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
              <section>
                <SectionHeading>Recent conversations</SectionHeading>
                <RecentConversationsList organizationId={selectedOrganizationId} />
              </section>

              <section>
                <SectionHeading>Pending recommendations</SectionHeading>
                <PendingRecommendationsList organizationId={selectedOrganizationId} />
              </section>

              <section>
                <SectionHeading>Memory</SectionHeading>
                <MemoryList organizationId={selectedOrganizationId} />
              </section>
            </div>
          </div>
        )}
      </SectionState>
    </div>
  );
}
