"use client";

import { PageHeader } from "@/components/navigation/page-header";
import { AiAssistantSubNav } from "@/features/ai-assistant/components/ai-assistant-sub-nav";
import { DocumentList } from "@/features/ai-assistant/components/document-list";
import { IngestDocumentForm } from "@/features/ai-assistant/components/ingest-document-form";
import { KnowledgeSearchPanel } from "@/features/ai-assistant/components/knowledge-search-panel";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { typography } from "@/lib/typography";
import { usePermissions } from "@/permissions/hooks";
import { useSelectedOrganization } from "@/organization/use-organizations";
import { cn } from "@/utils/cn";

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className={cn(typography.cardTitle, "mb-3")}>{children}</h2>;
}

/** `/intelligence/knowledge` (§26-adjacent). */
export function KnowledgePage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const { can } = usePermissions();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Knowledge" description="Documents ingested for retrieval, and a preview of what the assistant would find." />
      <AiAssistantSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-8">
            <section>
              <SectionHeading>Search preview</SectionHeading>
              <KnowledgeSearchPanel organizationId={selectedOrganizationId} />
            </section>

            <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              <section>
                <SectionHeading>Documents</SectionHeading>
                <DocumentList organizationId={selectedOrganizationId} />
              </section>

              {can("create") && (
                <section>
                  <SectionHeading>Ingest a document</SectionHeading>
                  <IngestDocumentForm organizationId={selectedOrganizationId} />
                </section>
              )}
            </div>
          </div>
        )}
      </SectionState>
    </div>
  );
}
