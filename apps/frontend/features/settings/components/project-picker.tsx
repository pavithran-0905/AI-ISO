"use client";

import { FormField } from "@/components/forms/form-field";
import { Select } from "@/components/forms/select";
import type { ProjectSummary } from "@/features/settings/types";

/** A real project list (`GET /projects?organization_id=`, unbounded,
 * server-side visibility-filtered) — Settings has no existing
 * "selected project" concept (unlike organization), so this picker is
 * scoped to this page only, not a global store. */
export function ProjectPicker({
  projects,
  selectedProjectId,
  onSelect,
}: {
  projects: ProjectSummary[];
  selectedProjectId: string | null;
  onSelect: (projectId: string) => void;
}) {
  return (
    <FormField label="Project">
      {(fieldProps) => (
        <Select {...fieldProps} value={selectedProjectId ?? ""} onChange={(event) => onSelect(event.target.value)} className="max-w-sm">
          <option value="" disabled>
            Choose a project…
          </option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.displayName ?? project.name}
            </option>
          ))}
        </Select>
      )}
    </FormField>
  );
}
