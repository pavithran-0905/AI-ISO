"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { PageHeader } from "@/components/navigation/page-header";
import { GroupCreateForm } from "@/features/infrastructure/components/group-create-form";
import { GroupList } from "@/features/infrastructure/components/group-list";
import { GroupMembersDrawer } from "@/features/infrastructure/components/group-members-drawer";
import { InfrastructureSubNav } from "@/features/infrastructure/components/infrastructure-sub-nav";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useCreateGroup } from "@/features/infrastructure/hooks/use-groups";
import type { AssetGroup } from "@/features/infrastructure/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** `/infrastructure/groups`. No delete or add/remove-member route
 * exists (confirmed absent) — a group's membership is fixed at
 * creation time in this UI, and there is no delete action to offer. */
export function GroupsListPage() {
  const { can } = usePermissions();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } =
    useSelectedOrganization();
  const [selectedGroup, setSelectedGroup] = useState<AssetGroup | null>(null);
  const createGroup = useCreateGroup();

  async function handleCreate(input: Parameters<typeof createGroup.mutateAsync>[0]) {
    try {
      await createGroup.mutateAsync(input);
      toast.success("Group created");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not create group", message);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Groups" description="Static, dynamic, and rule-based asset groups." />
      <InfrastructureSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <div className="flex flex-col gap-6">
            {can("create") && (
              <GroupCreateForm organizationId={selectedOrganizationId} onSubmit={handleCreate} isSubmitting={createGroup.isPending} />
            )}
            <GroupList organizationId={selectedOrganizationId} onSelect={setSelectedGroup} />
          </div>
        )}
      </SectionState>

      <GroupMembersDrawer group={selectedGroup} onClose={() => setSelectedGroup(null)} />
    </div>
  );
}
