"use client";

import { PageHeader } from "@/components/navigation/page-header";
import { Alert } from "@/components/feedback/alert";
import { AdministrationSubNav } from "@/features/administration/components/administration-sub-nav";
import { useRbacPermissions } from "@/features/administration/hooks/use-rbac";
import { SectionState } from "@/features/dashboard/components/section-state";

/**
 * Permissions — `/administration/permissions` (§21). `rbac-service`'s
 * real fine-grained `resource`/`action`/`scope` permission catalog —
 * same "reference, not live" reasoning as Roles.
 */
export function PermissionsPage() {
  const permissionsQuery = useRbacPermissions();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Permissions" description="rbac-service's own fine-grained permission catalog." />
      <AdministrationSubNav />

      <Alert tone="warning" title="Reference catalog, not the live enforcement mechanism">
        Same as Roles — this is real, but not what any other AI-IOS service actually checks when deciding what a user
        can do.
      </Alert>

      <SectionState
        isLoading={permissionsQuery.isLoading}
        isError={permissionsQuery.isError}
        error={permissionsQuery.error}
        onRetry={() => permissionsQuery.refetch()}
        skeletonClassName="h-96 w-full"
      >
        {permissionsQuery.data && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-border border-b">
                  <th scope="col" className="px-3 py-2 font-medium">
                    Name
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Resource
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Action
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Scope
                  </th>
                </tr>
              </thead>
              <tbody>
                {permissionsQuery.data.map((permission) => (
                  <tr key={permission.id} className="border-border hover:bg-muted/50 border-b last:border-0">
                    <td className="px-3 py-2">
                      <p className="font-medium">{permission.name}</p>
                      {permission.description && <p className="text-muted-foreground text-xs">{permission.description}</p>}
                    </td>
                    <td className="text-muted-foreground px-3 py-2 font-mono text-xs">{permission.resource}</td>
                    <td className="text-muted-foreground px-3 py-2 font-mono text-xs">{permission.action}</td>
                    <td className="text-muted-foreground px-3 py-2 font-mono text-xs">{permission.scope}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionState>
    </div>
  );
}
