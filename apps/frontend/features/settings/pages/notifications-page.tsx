"use client";

import { usePathname } from "next/navigation";

import { SettingsLayout } from "@/layouts/settings-layout";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { NotificationChannelsSection } from "@/features/settings/components/notification-channels-section";
import { NotificationPreferencesForm } from "@/features/settings/components/notification-preferences-form";
import { renderSettingsNavLink } from "@/features/settings/components/settings-nav-link";
import { useNotificationPreferences } from "@/features/settings/hooks/use-notification-settings";
import { useSettingsNavItems } from "@/features/settings/lib/nav-items";
import { useSelectedOrganization } from "@/organization/use-organizations";
import { usePermissions } from "@/permissions/hooks";

/** Notifications — `/settings/notifications` (§15). Per-user
 * preferences (real, partial-safe) and organization-level channel
 * configuration (real, admin-gated) are two distinct concepts, shown
 * as two independent sections. */
export function NotificationsPage() {
  const pathname = usePathname();
  const navItems = useSettingsNavItems();
  const { isAdministrative } = usePermissions();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } = useSelectedOrganization();
  const preferencesQuery = useNotificationPreferences(selectedOrganizationId);

  return (
    <SettingsLayout title="Notifications" navItems={navItems} activeHref={pathname} renderNavLink={renderSettingsNavLink}>
      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-6">
            <SectionState isLoading={preferencesQuery.isLoading} isError={preferencesQuery.isError} error={preferencesQuery.error} onRetry={() => preferencesQuery.refetch()}>
              {preferencesQuery.data && <NotificationPreferencesForm organizationId={selectedOrganizationId} preferences={preferencesQuery.data} />}
            </SectionState>
            <NotificationChannelsSection organizationId={selectedOrganizationId} canEdit={isAdministrative} />
          </div>
        )}
      </SectionState>
    </SettingsLayout>
  );
}
