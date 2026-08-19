"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useOrganizationLicense, useOrganizationQuota } from "@/features/settings/hooks/use-organization-settings";

/**
 * `GET /organizations/{id}/licenses` and `.../quotas` — read-only in
 * this feature. Editing a license or quota is naturally a billing-
 * administration action, not a general organization self-service
 * setting — the separate, still-`planned()` "Licensing & Billing"
 * route registry entry (`docs/frontend/backend-feature-matrix.md`
 * doc 070-adjacent) is the intended future home for that; nothing
 * here duplicates or anticipates it.
 */
export function OrganizationPlanSection({ organizationId }: { organizationId: string }) {
  const licenseQuery = useOrganizationLicense(organizationId);
  const quotaQuery = useOrganizationQuota(organizationId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Plan &amp; limits</CardTitle>
        <CardDescription>Read-only — managed through billing administration, not here.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <SectionState isLoading={licenseQuery.isLoading} isError={licenseQuery.isError} error={licenseQuery.error} onRetry={() => licenseQuery.refetch()}>
          {licenseQuery.data && (
            <div className="text-sm">
              <p className="font-medium">{licenseQuery.data.licenseType}</p>
              <p className="text-muted-foreground text-xs">
                {licenseQuery.data.consumedSeats} of {licenseQuery.data.seatCount} seats used · {licenseQuery.data.status}
                {licenseQuery.data.expiresAt ? ` · Expires ${new Date(licenseQuery.data.expiresAt).toLocaleDateString()}` : ""}
              </p>
            </div>
          )}
        </SectionState>

        <SectionState isLoading={quotaQuery.isLoading} isError={quotaQuery.isError} error={quotaQuery.error} onRetry={() => quotaQuery.refetch()}>
          {quotaQuery.data && (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
              <Limit label="Users" value={quotaQuery.data.maxUsers} />
              <Limit label="Projects" value={quotaQuery.data.maxProjects} />
              <Limit label="Assets" value={quotaQuery.data.maxAssets} />
              <Limit label="Storage (GB)" value={quotaQuery.data.maxStorageGb} />
              <Limit label="Workflows" value={quotaQuery.data.maxWorkflows} />
              <Limit label="Automation jobs" value={quotaQuery.data.maxAutomationJobs} />
              <Limit label="Connectors" value={quotaQuery.data.maxConnectors} />
              <Limit label="API calls/day" value={quotaQuery.data.maxApiCallsPerDay} />
              <Limit label="AI requests/day" value={quotaQuery.data.maxAiRequestsPerDay} />
            </dl>
          )}
        </SectionState>
      </CardContent>
    </Card>
  );
}

function Limit({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="tabular-nums">{value.toLocaleString()}</dd>
    </div>
  );
}
