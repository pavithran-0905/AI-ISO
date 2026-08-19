"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/navigation/page-header";
import { EmptyState } from "@/components/feedback/empty-state";
import { IconButton } from "@/components/ui/icon-button";
import { AdministrationSubNav } from "@/features/administration/components/administration-sub-nav";
import { TeamFormDialog } from "@/features/administration/components/team-form-dialog";
import { TeamList } from "@/features/administration/components/team-list";
import { useTeams } from "@/features/administration/hooks/use-teams";
import type { Team } from "@/features/administration/types";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useSelectedOrganization } from "@/organization/use-organizations";

/** Teams — `/administration/teams` (§22). No team-members endpoint
 * exists anywhere (confirmed absent) — list/create/edit/delete only,
 * matching the real backend surface exactly. */
export function TeamsPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } = useSelectedOrganization();
  const teamsQuery = useTeams(selectedOrganizationId);
  const [formOpen, setFormOpen] = useState(false);
  const [editingTeam, setEditingTeam] = useState<Team | null>(null);

  function openCreate() {
    setEditingTeam(null);
    setFormOpen(true);
  }

  function openEdit(team: Team) {
    setEditingTeam(team);
    setFormOpen(true);
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Teams"
        description="Organization teams — real identity and metadata; no membership roster exists to manage here."
        primaryAction={
          selectedOrganizationId ? <IconButton icon={Plus} aria-label="Create team" variant="outline" onClick={openCreate} /> : undefined
        }
      />
      <AdministrationSubNav />

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <SectionState isLoading={teamsQuery.isLoading} isError={teamsQuery.isError} error={teamsQuery.error} onRetry={() => teamsQuery.refetch()}>
            {teamsQuery.data &&
              (teamsQuery.data.length === 0 ? (
                <EmptyState title="No teams found" description="Create one to get started." />
              ) : (
                <TeamList teams={teamsQuery.data} onEdit={openEdit} />
              ))}
          </SectionState>
        )}
      </SectionState>

      {selectedOrganizationId && (
        <TeamFormDialog organizationId={selectedOrganizationId} team={editingTeam} open={formOpen} onClose={() => setFormOpen(false)} />
      )}
    </div>
  );
}
