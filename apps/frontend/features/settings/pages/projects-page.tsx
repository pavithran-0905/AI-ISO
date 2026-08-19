"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

import { SettingsLayout } from "@/layouts/settings-layout";
import { EmptyState } from "@/components/feedback/empty-state";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ProjectIdentityForm } from "@/features/settings/components/project-identity-form";
import { ProjectPicker } from "@/features/settings/components/project-picker";
import { ProjectSettingsForm } from "@/features/settings/components/project-settings-form";
import { renderSettingsNavLink } from "@/features/settings/components/settings-nav-link";
import { useOrganizationProjects, useProjectSettings } from "@/features/settings/hooks/use-project-settings";
import { useSettingsNavItems } from "@/features/settings/lib/nav-items";
import { useSelectedOrganization } from "@/organization/use-organizations";
import { usePermissions } from "@/permissions/hooks";

/**
 * Projects — `/settings/projects` (§8). No global "selected project"
 * concept exists elsewhere in this app — the picker here is scoped to
 * this page only. Same coarse-permission-heuristic reasoning as
 * Organization: real per-project Administrator rank can't be verified
 * client-side, so `canEdit` is a UX convenience, not a security
 * boundary.
 */
export function ProjectsPage() {
  const pathname = usePathname();
  const navItems = useSettingsNavItems();
  const { isAdministrative } = usePermissions();
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } = useSelectedOrganization();
  const projectsQuery = useOrganizationProjects(selectedOrganizationId);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const settingsQuery = useProjectSettings(selectedProjectId);

  const selectedProject = projectsQuery.data?.find((project) => project.id === selectedProjectId) ?? null;

  return (
    <SettingsLayout title="Projects" navItems={navItems} activeHref={pathname} renderNavLink={renderSettingsNavLink}>
      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <SectionState isLoading={projectsQuery.isLoading} isError={projectsQuery.isError} error={projectsQuery.error} onRetry={() => projectsQuery.refetch()}>
            {projectsQuery.data &&
              (projectsQuery.data.length === 0 ? (
                <EmptyState title="No projects yet" description="This organization has no projects to configure." />
              ) : (
                <div className="flex flex-col gap-6">
                  <ProjectPicker projects={projectsQuery.data} selectedProjectId={selectedProjectId} onSelect={setSelectedProjectId} />

                  {selectedProject && (
                    <>
                      <ProjectIdentityForm project={selectedProject} canEdit={isAdministrative} />
                      <SectionState isLoading={settingsQuery.isLoading} isError={settingsQuery.isError} error={settingsQuery.error} onRetry={() => settingsQuery.refetch()}>
                        {settingsQuery.data && (
                          <ProjectSettingsForm projectId={selectedProject.id} settings={settingsQuery.data} canEdit={isAdministrative} />
                        )}
                      </SectionState>
                    </>
                  )}
                </div>
              ))}
          </SectionState>
        )}
      </SectionState>
    </SettingsLayout>
  );
}
