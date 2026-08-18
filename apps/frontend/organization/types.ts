/**
 * Organization types mirroring the real backend contract
 * (`services/organization-service/app/api/organization.py`,
 * `app/api/analytics.py`), confirmed by direct source inspection.
 *
 * Why this module exists: almost every business V1 endpoint (alerts,
 * assets, automation, reports, org analytics itself) requires
 * `organization_id` as a required parameter, but the current login
 * contract doesn't populate an `organization_id` JWT claim (the
 * documented gap in `@/auth/types`). `GET /organizations` itself needs
 * no `organization_id` — just auth — so this module lets the frontend
 * ask "which organizations can this user see" and hold a selection in
 * memory, unblocking every org-scoped read without inventing or
 * guessing at any value. See
 * `docs/frontend/developer-guide/dashboard.md` for the full rationale.
 */

export interface Organization {
  id: string;
  name: string;
  displayName: string;
  shortName: string | null;
  slug: string;
  status: string;
}

/** `OrganizationStatisticsResponse` per `app/api/analytics.py` — the
 * real source for every KPI the dashboard shows; nothing here is
 * derived or estimated. */
export interface OrganizationStatistics {
  organizationId: string;
  userCount: number;
  projectCount: number;
  assetCount: number;
  workflowCount: number;
  automationCount: number;
  validationCount: number;
  computedAt: string;
}
