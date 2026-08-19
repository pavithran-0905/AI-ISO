"use client";

import { useState } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { Alert } from "@/components/feedback/alert";
import { Card, CardContent } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { AdministrationSubNav } from "@/features/administration/components/administration-sub-nav";
import { RoleDetailDrawer } from "@/features/administration/components/role-detail-drawer";
import { useRbacRoles } from "@/features/administration/hooks/use-rbac";
import type { RbacRole } from "@/features/administration/types";
import { SectionState } from "@/features/dashboard/components/section-state";

/**
 * Roles — `/administration/roles` (§18). `rbac-service`'s real
 * 10-role catalog, read-only (create/update/delete exist and require
 * `settings:manage`, but editing an inert catalog with no other
 * consumer wasn't built here — see the developer guide's scope
 * reasoning). Confirmed unused by any live authorization decision
 * elsewhere in the platform — the banner says so, not just the docs.
 */
export function RolesPage() {
  const rolesQuery = useRbacRoles();
  const [selectedRole, setSelectedRole] = useState<RbacRole | null>(null);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Roles" description="rbac-service's own role catalog." />
      <AdministrationSubNav />

      <Alert tone="warning" title="Reference catalog, not the live enforcement mechanism">
        No other AI-IOS service reads from rbac-service&apos;s tables when deciding what a user can do — every service
        checks the caller&apos;s own JWT role claim locally instead. This list is real and accurate; it just isn&apos;t
        what actually gates access elsewhere in the platform today.
      </Alert>

      <SectionState isLoading={rolesQuery.isLoading} isError={rolesQuery.isError} error={rolesQuery.error} onRetry={() => rolesQuery.refetch()} skeletonClassName="h-96 w-full">
        {rolesQuery.data && (
          <ul className="flex flex-col gap-2">
            {rolesQuery.data.map((role) => (
              <li key={role.id}>
                <button type="button" onClick={() => setSelectedRole(role)} className="w-full text-left">
                  <Card className="hover:border-muted-foreground/50 transition-colors">
                    <CardContent className="flex items-center justify-between gap-3 p-4">
                      <div>
                        <p className="text-sm font-medium">
                          {role.name} <span className="text-muted-foreground font-mono text-xs">({role.code})</span>
                        </p>
                        {role.description && <p className="text-muted-foreground text-xs">{role.description}</p>}
                      </div>
                      <StatusBadge tone={role.isSystem ? "info" : "neutral"} label={role.isSystem ? "System" : "Custom"} />
                    </CardContent>
                  </Card>
                </button>
              </li>
            ))}
          </ul>
        )}
      </SectionState>

      <RoleDetailDrawer role={selectedRole} onClose={() => setSelectedRole(null)} />
    </div>
  );
}
