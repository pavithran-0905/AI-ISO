"use client";

import { Plus } from "lucide-react";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { SettingsLayout } from "@/layouts/settings-layout";
import { EmptyState } from "@/components/feedback/empty-state";
import { IconButton } from "@/components/ui/icon-button";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ConnectorList } from "@/features/settings/components/connector-list";
import { CreateConnectorDialog } from "@/features/settings/components/create-connector-dialog";
import { renderSettingsNavLink } from "@/features/settings/components/settings-nav-link";
import { useConnectors } from "@/features/settings/hooks/use-integrations";
import { useSettingsNavItems } from "@/features/settings/lib/nav-items";
import { useSelectedOrganization } from "@/organization/use-organizations";

/**
 * Integrations — `/settings/integrations` (§10). No permission check
 * exists on any route in this service beyond a valid JWT (confirmed
 * absent) — every authenticated member can register/configure/test/
 * enable/disable/remove a connector. Shown to everyone accordingly,
 * matching the real backend, not an invented restriction.
 */
export function IntegrationsListPage() {
  const pathname = usePathname();
  const navItems = useSettingsNavItems();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } = useSelectedOrganization();
  const connectorsQuery = useConnectors(selectedOrganizationId);
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <SettingsLayout
      title="Integrations"
      navItems={navItems}
      activeHref={pathname}
      renderNavLink={renderSettingsNavLink}
      actions={
        selectedOrganizationId ? (
          <IconButton icon={Plus} aria-label="Register connector" variant="outline" onClick={() => setCreateOpen(true)} />
        ) : undefined
      }
    >
      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <SectionState isLoading={connectorsQuery.isLoading} isError={connectorsQuery.isError} error={connectorsQuery.error} onRetry={() => connectorsQuery.refetch()}>
            {connectorsQuery.data &&
              (connectorsQuery.data.length === 0 ? (
                <EmptyState title="No integrations configured" description="Register a connector to link AI-IOS with another system." />
              ) : (
                <ConnectorList connectors={connectorsQuery.data} />
              ))}
          </SectionState>
        )}
      </SectionState>

      {selectedOrganizationId && (
        <CreateConnectorDialog organizationId={selectedOrganizationId} open={createOpen} onClose={() => setCreateOpen(false)} />
      )}
    </SettingsLayout>
  );
}
