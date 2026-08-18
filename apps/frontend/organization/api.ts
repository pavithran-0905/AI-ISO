import { apiClient } from "@/api/client";
import type { Organization, OrganizationStatistics } from "@/organization/types";

interface OrganizationResponseBody {
  id: string;
  name: string;
  display_name: string;
  short_name: string | null;
  slug: string;
  status: string;
}

interface OrganizationStatisticsResponseBody {
  organization_id: string;
  user_count: number;
  project_count: number;
  asset_count: number;
  workflow_count: number;
  automation_count: number;
  validation_count: number;
  computed_at: string;
}

function toOrganization(body: OrganizationResponseBody): Organization {
  return {
    id: body.id,
    name: body.name,
    displayName: body.display_name,
    shortName: body.short_name,
    slug: body.slug,
    status: body.status,
  };
}

function toOrganizationStatistics(body: OrganizationStatisticsResponseBody): OrganizationStatistics {
  return {
    organizationId: body.organization_id,
    userCount: body.user_count,
    projectCount: body.project_count,
    assetCount: body.asset_count,
    workflowCount: body.workflow_count,
    automationCount: body.automation_count,
    validationCount: body.validation_count,
    computedAt: body.computed_at,
  };
}

export const organizationApi = {
  async list(): Promise<Organization[]> {
    const body = await apiClient.get<OrganizationResponseBody[]>("/organizations");
    return body.map(toOrganization);
  },

  async fetchStatistics(organizationId: string): Promise<OrganizationStatistics> {
    const body = await apiClient.get<OrganizationStatisticsResponseBody>(
      `/organizations/${organizationId}/analytics`,
    );
    return toOrganizationStatistics(body);
  },
};
