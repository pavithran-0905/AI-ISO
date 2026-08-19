"use client";

import { PageHeader } from "@/components/navigation/page-header";
import { CriticalIssuesSection } from "@/features/infrastructure/components/critical-issues-section";
import { InfrastructureStatisticsSummary } from "@/features/infrastructure/components/infrastructure-statistics-summary";
import { InfrastructureSubNav } from "@/features/infrastructure/components/infrastructure-sub-nav";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { typography } from "@/lib/typography";
import { useSelectedOrganization } from "@/organization/use-organizations";
import { cn } from "@/utils/cn";

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className={cn(typography.cardTitle, "mb-3")}>{children}</h2>;
}

/**
 * Infrastructure Overview (§5) — "What assets exist? What types? What
 * requires attention? What changed recently?" all answered from real
 * `GET /inventory/analytics`/`GET /inventory/search` data. Mirrors
 * Monitoring's/Alerting's/Reporting's own overview structure (sub-nav
 * + summary sections).
 */
export function InfrastructureOverviewPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Infrastructure" description="Authoritative CMDB: every discovered asset, relationships, topology." />
      <InfrastructureSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-8">
            <section>
              <SectionHeading>Summary</SectionHeading>
              <InfrastructureStatisticsSummary organizationId={selectedOrganizationId} />
            </section>

            <section>
              <SectionHeading>Needs attention</SectionHeading>
              <CriticalIssuesSection organizationId={selectedOrganizationId} />
            </section>
          </div>
        )}
      </SectionState>
    </div>
  );
}
