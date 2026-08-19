/**
 * `services/organization-service` — `/organizations/{id}`,
 * `/organizations/{id}/settings`, `/organizations/{id}/branding`,
 * `/organizations/{id}/licenses`, `/organizations/{id}/quotas`. Every
 * write route requires the caller hold Administrator rank *within
 * that organization* (`require_admin`) — a real per-org membership
 * role the frontend's own coarse `role` claim cannot verify (see the
 * developer guide's Permissions section).
 */

import { apiClient } from "@/api/client";
import type {
  OrganizationBranding,
  OrganizationIdentity,
  OrganizationLicense,
  OrganizationQuota,
  OrganizationSettings,
  UpdateOrganizationBrandingInput,
  UpdateOrganizationIdentityInput,
  UpdateOrganizationSettingsInput,
} from "@/features/settings/types";

interface OrganizationResponseBody {
  id: string;
  slug: string;
  name: string;
  display_name: string | null;
  short_name: string | null;
  description: string | null;
  status: string;
  primary_domain: string | null;
  primary_contact_email: string | null;
  logo_url: string | null;
  website: string | null;
  industry: string | null;
  timezone: string;
  language: string;
  country: string | null;
  currency: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

function toIdentity(body: OrganizationResponseBody): OrganizationIdentity {
  return {
    id: body.id,
    slug: body.slug,
    name: body.name,
    displayName: body.display_name,
    shortName: body.short_name,
    description: body.description,
    status: body.status,
    primaryDomain: body.primary_domain,
    primaryContactEmail: body.primary_contact_email,
    logoUrl: body.logo_url,
    website: body.website,
    industry: body.industry,
    timezone: body.timezone,
    language: body.language,
    country: body.country,
    currency: body.currency,
    metadata: body.metadata,
    createdAt: body.created_at,
    updatedAt: body.updated_at,
  };
}

interface OrganizationSettingsBody {
  password_policy: Record<string, unknown>;
  mfa_enforced: boolean;
  allowed_domains: string[];
  default_language: string;
  default_timezone: string;
  session_timeout_minutes: number;
  data_retention_days: number;
  storage_policy: Record<string, unknown>;
  notification_policy: Record<string, unknown>;
}

function toSettings(body: OrganizationSettingsBody): OrganizationSettings {
  return {
    passwordPolicy: body.password_policy,
    mfaEnforced: body.mfa_enforced,
    allowedDomains: body.allowed_domains,
    defaultLanguage: body.default_language,
    defaultTimezone: body.default_timezone,
    sessionTimeoutMinutes: body.session_timeout_minutes,
    dataRetentionDays: body.data_retention_days,
    storagePolicy: body.storage_policy,
    notificationPolicy: body.notification_policy,
  };
}

interface OrganizationBrandingBody {
  logo_url: string | null;
  dark_logo_url: string | null;
  favicon_url: string | null;
  primary_color: string | null;
  secondary_color: string | null;
  theme: string;
  email_templates: Record<string, unknown>;
  login_screen_branding: Record<string, unknown>;
  dashboard_branding: Record<string, unknown>;
}

function toBranding(body: OrganizationBrandingBody): OrganizationBranding {
  return {
    logoUrl: body.logo_url,
    darkLogoUrl: body.dark_logo_url,
    faviconUrl: body.favicon_url,
    primaryColor: body.primary_color,
    secondaryColor: body.secondary_color,
    theme: body.theme,
    emailTemplates: body.email_templates,
    loginScreenBranding: body.login_screen_branding,
    dashboardBranding: body.dashboard_branding,
  };
}

interface OrganizationLicenseBody {
  license_type: string;
  seat_count: number;
  consumed_seats: number;
  status: string;
  expires_at: string | null;
  grace_period_days: number;
  activated_at: string | null;
}

interface OrganizationQuotaBody {
  max_users: number;
  max_projects: number;
  max_assets: number;
  max_storage_gb: number;
  max_workflows: number;
  max_automation_jobs: number;
  max_connectors: number;
  max_api_calls_per_day: number;
  max_ai_requests_per_day: number;
  max_plugins: number;
}

export const organizationApi = {
  async getIdentity(organizationId: string): Promise<OrganizationIdentity> {
    const body = await apiClient.get<OrganizationResponseBody>(`/organizations/${organizationId}`);
    return toIdentity(body);
  },

  /** Full-replace `PUT` (confirmed: no `PATCH` route exists for this
   * resource) — always resend the complete object. */
  async updateIdentity(organizationId: string, input: UpdateOrganizationIdentityInput): Promise<OrganizationIdentity> {
    const body = await apiClient.put<OrganizationResponseBody>(`/organizations/${organizationId}`, {
      name: input.name,
      display_name: input.displayName,
      short_name: input.shortName,
      description: input.description,
      status: input.status,
      primary_domain: input.primaryDomain,
      primary_contact_email: input.primaryContactEmail,
      logo_url: input.logoUrl,
      website: input.website,
      industry: input.industry,
      timezone: input.timezone,
      language: input.language,
      country: input.country,
      currency: input.currency,
      metadata: input.metadata,
    });
    return toIdentity(body);
  },

  async getSettings(organizationId: string): Promise<OrganizationSettings> {
    const body = await apiClient.get<OrganizationSettingsBody>(`/organizations/${organizationId}/settings`);
    return toSettings(body);
  },

  async updateSettings(organizationId: string, input: UpdateOrganizationSettingsInput): Promise<OrganizationSettings> {
    const body = await apiClient.put<OrganizationSettingsBody>(`/organizations/${organizationId}/settings`, {
      password_policy: input.passwordPolicy,
      mfa_enforced: input.mfaEnforced,
      allowed_domains: input.allowedDomains,
      default_language: input.defaultLanguage,
      default_timezone: input.defaultTimezone,
      session_timeout_minutes: input.sessionTimeoutMinutes,
      data_retention_days: input.dataRetentionDays,
      storage_policy: input.storagePolicy,
      notification_policy: input.notificationPolicy,
    });
    return toSettings(body);
  },

  async getBranding(organizationId: string): Promise<OrganizationBranding> {
    const body = await apiClient.get<OrganizationBrandingBody>(`/organizations/${organizationId}/branding`);
    return toBranding(body);
  },

  async updateBranding(organizationId: string, input: UpdateOrganizationBrandingInput): Promise<OrganizationBranding> {
    const body = await apiClient.put<OrganizationBrandingBody>(`/organizations/${organizationId}/branding`, {
      logo_url: input.logoUrl,
      dark_logo_url: input.darkLogoUrl,
      favicon_url: input.faviconUrl,
      primary_color: input.primaryColor,
      secondary_color: input.secondaryColor,
      theme: input.theme,
      email_templates: input.emailTemplates,
      login_screen_branding: input.loginScreenBranding,
      dashboard_branding: input.dashboardBranding,
    });
    return toBranding(body);
  },

  /** Read-only in this feature — see `OrganizationLicense`'s own
   * docstring for why editing isn't built here. */
  async getLicense(organizationId: string): Promise<OrganizationLicense> {
    const body = await apiClient.get<OrganizationLicenseBody>(`/organizations/${organizationId}/licenses`);
    return {
      licenseType: body.license_type,
      seatCount: body.seat_count,
      consumedSeats: body.consumed_seats,
      status: body.status,
      expiresAt: body.expires_at,
      gracePeriodDays: body.grace_period_days,
      activatedAt: body.activated_at,
    };
  },

  async getQuota(organizationId: string): Promise<OrganizationQuota> {
    const body = await apiClient.get<OrganizationQuotaBody>(`/organizations/${organizationId}/quotas`);
    return {
      maxUsers: body.max_users,
      maxProjects: body.max_projects,
      maxAssets: body.max_assets,
      maxStorageGb: body.max_storage_gb,
      maxWorkflows: body.max_workflows,
      maxAutomationJobs: body.max_automation_jobs,
      maxConnectors: body.max_connectors,
      maxApiCallsPerDay: body.max_api_calls_per_day,
      maxAiRequestsPerDay: body.max_ai_requests_per_day,
      maxPlugins: body.max_plugins,
    };
  },
};
