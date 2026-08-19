/**
 * `services/organization-service` — `GET/POST /organizations/{id}/teams`,
 * `PUT/DELETE /teams/{id}`. No single-team `GET` route exists
 * (confirmed absent — only list, and flat update/delete); no
 * team-members endpoint exists at all (confirmed absent — team
 * membership at the API level has no representation anywhere in this
 * service today).
 */

import { apiClient } from "@/api/client";
import type { CreateTeamInput, Team, UpdateTeamInput } from "@/features/administration/types";

interface TeamResponseBody {
  id: string;
  organization_id: string;
  name: string;
  code: string | null;
  description: string | null;
  department_id: string | null;
  business_unit_id: string | null;
  team_lead_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

function toTeam(body: TeamResponseBody): Team {
  return {
    id: body.id,
    organizationId: body.organization_id,
    name: body.name,
    code: body.code,
    description: body.description,
    departmentId: body.department_id,
    businessUnitId: body.business_unit_id,
    teamLeadId: body.team_lead_id,
    metadata: body.metadata,
    createdAt: body.created_at,
    updatedAt: body.updated_at,
  };
}

export const teamsApi = {
  async listForOrganization(organizationId: string): Promise<Team[]> {
    const body = await apiClient.get<TeamResponseBody[]>(`/organizations/${organizationId}/teams`);
    return body.map(toTeam);
  },

  async create(input: CreateTeamInput): Promise<Team> {
    const body = await apiClient.post<TeamResponseBody>(`/organizations/${input.organizationId}/teams`, {
      name: input.name,
      code: input.code,
      description: input.description,
      department_id: input.departmentId,
      team_lead_id: input.teamLeadId,
    });
    return toTeam(body);
  },

  async update(teamId: string, input: UpdateTeamInput): Promise<Team> {
    const body = await apiClient.put<TeamResponseBody>(`/teams/${teamId}`, {
      name: input.name,
      code: input.code,
      description: input.description,
      department_id: input.departmentId,
      team_lead_id: input.teamLeadId,
    });
    return toTeam(body);
  },

  async remove(teamId: string): Promise<void> {
    await apiClient.delete(`/teams/${teamId}`);
  },
};
