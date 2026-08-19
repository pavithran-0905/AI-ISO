"use client";

import { usePathname } from "next/navigation";

import { SettingsLayout } from "@/layouts/settings-layout";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { OrganizationBrandingForm } from "@/features/settings/components/organization-branding-form";
import { OrganizationIdentityForm } from "@/features/settings/components/organization-identity-form";
import { OrganizationPlanSection } from "@/features/settings/components/organization-plan-section";
import { OrganizationPolicyForm } from "@/features/settings/components/organization-policy-form";
import { renderSettingsNavLink } from "@/features/settings/components/settings-nav-link";
import {
  useOrganizationBranding,
  useOrganizationIdentity,
  useOrganizationSettings,
} from "@/features/settings/hooks/use-organization-settings";
import { useSettingsNavItems } from "@/features/settings/lib/nav-items";
import { useSelectedOrganization } from "@/organization/use-organizations";
import { usePermissions } from "@/permissions/hooks";

/**
 * Organization — `/settings/organization` (§7). Every `GET` here only
 * requires organization membership; `PUT`s require Administrator rank
 * *within that organization* — a real per-org role this frontend
 * cannot verify (its own `role` claim is platform-wide, and often
 * unpopulated). `canEdit` uses the coarse `isAdministrative` heuristic
 * as a UX convenience only; the backend remains authoritative and
 * returns a real 403 on a mismatch. See the developer guide.
 */
export function OrganizationPage() {
  const pathname = usePathname();
  const navItems = useSettingsNavItems();
  const { isAdministrative } = usePermissions();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } = useSelectedOrganization();
  const identityQuery = useOrganizationIdentity(selectedOrganizationId);
  const settingsQuery = useOrganizationSettings(selectedOrganizationId);
  const brandingQuery = useOrganizationBranding(selectedOrganizationId);

  return (
    <SettingsLayout title="Organization" navItems={navItems} activeHref={pathname} renderNavLink={renderSettingsNavLink}>
      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-6">
            <SectionState isLoading={identityQuery.isLoading} isError={identityQuery.isError} error={identityQuery.error} onRetry={() => identityQuery.refetch()}>
              {identityQuery.data && <OrganizationIdentityForm identity={identityQuery.data} canEdit={isAdministrative} />}
            </SectionState>

            <SectionState isLoading={settingsQuery.isLoading} isError={settingsQuery.isError} error={settingsQuery.error} onRetry={() => settingsQuery.refetch()}>
              {settingsQuery.data && (
                <OrganizationPolicyForm organizationId={selectedOrganizationId} settings={settingsQuery.data} canEdit={isAdministrative} />
              )}
            </SectionState>

            <SectionState isLoading={brandingQuery.isLoading} isError={brandingQuery.isError} error={brandingQuery.error} onRetry={() => brandingQuery.refetch()}>
              {brandingQuery.data && (
                <OrganizationBrandingForm organizationId={selectedOrganizationId} branding={brandingQuery.data} canEdit={isAdministrative} />
              )}
            </SectionState>

            <OrganizationPlanSection organizationId={selectedOrganizationId} />
          </div>
        )}
      </SectionState>
    </SettingsLayout>
  );
}
