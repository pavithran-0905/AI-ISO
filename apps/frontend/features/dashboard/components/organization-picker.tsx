"use client";

import { Building2 } from "lucide-react";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import type { Organization } from "@/organization/types";
import { useOrganizationStore } from "@/organization/store";

/**
 * Shown when the signed-in user belongs to more than one organization
 * and none is selected yet (`@/organization/use-organizations`'s
 * `needsSelection`) — every organization-scoped V1 endpoint requires a
 * specific `organization_id`, so the dashboard can't reasonably guess
 * which one to show.
 */
export function OrganizationPicker({ organizations }: { organizations: Organization[] }) {
  const setSelectedOrganizationId = useOrganizationStore((state) => state.setSelectedOrganizationId);

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-6">
        <div className="flex items-center gap-2">
          <Building2 className="text-muted-foreground size-5" aria-hidden="true" />
          <h2 className="text-sm font-semibold">Choose an organization</h2>
        </div>
        <p className="text-muted-foreground text-sm">
          You have access to {organizations.length} organizations. Select one to see its dashboard.
        </p>
        <div className="flex flex-wrap gap-2">
          {organizations.map((org) => (
            <Button key={org.id} variant="outline" onClick={() => setSelectedOrganizationId(org.id)}>
              {org.displayName}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/** Shown when the user has zero organizations — the honest first-time
 * / no-access state (§31), never fake sample data. */
export function NoOrganizationAccessState() {
  return (
    <EmptyState
      icon={Building2}
      title="No organization access yet"
      description="Your account isn't a member of any organization, so there's no data to show. Contact your administrator to be added to one."
    />
  );
}
