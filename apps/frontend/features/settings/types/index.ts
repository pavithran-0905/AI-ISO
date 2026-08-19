/**
 * Types mirroring real V1 responses this feature consumes, confirmed
 * by direct source inspection across seven services (no dedicated
 * "settings-service" exists — confirmed absent from `services/`).
 * See `docs/frontend/developer-guide/settings.md` for the endpoint
 * each one comes from and every mutation-semantics/concurrency/
 * permission gap this typing doesn't paper over.
 */

// ---- My Preferences (user-management-service) --------------------------------------

/**
 * `PreferencesResponse` (`GET/PUT /users/preferences`). `theme`,
 * `dashboardPreferences`, `notificationPreferences`, and
 * `accessibility` are real fields this feature deliberately does not
 * expose as editable controls (see the developer guide's "Why theme
 * stays local" and "Opaque preference blobs" sections) — they're still
 * modeled here and round-tripped unchanged on every save, since `PUT`
 * resets any omitted field to its schema default rather than leaving
 * it alone.
 */
export interface UserPreferences {
  userId: string;
  language: string;
  theme: string;
  timezone: string;
  dateFormat: string;
  timeFormat: string;
  dashboardPreferences: Record<string, unknown>;
  notificationPreferences: Record<string, unknown>;
  accessibility: Record<string, unknown>;
  defaultOrganizationId: string | null;
  defaultProjectId: string | null;
}

/** `PreferencesUpdateRequest` — every field required on the wire; a
 * full-replace `PUT` with schema defaults for anything omitted
 * (confirmed: `UserPreferencesService.update` overwrites every
 * attribute unconditionally). The form always resends the complete,
 * last-fetched object with only the touched field(s) changed. */
export type UpdateUserPreferencesInput = Omit<UserPreferences, "userId">;

/** `ProfileResponse` (`GET/PUT /users/profile`, user-management-service
 * — distinct from `authentication-service`'s own read-only
 * `/auth/profile`). `customFields` is round-tripped unchanged, same
 * PUT-reset reasoning as above. */
export interface UserProfile {
  userId: string;
  biography: string | null;
  jobTitle: string | null;
  department: string | null;
  employeeId: string | null;
  managerId: string | null;
  customFields: Record<string, unknown>;
  profilePhoto: string | null;
}

export type UpdateUserProfileInput = Omit<UserProfile, "userId" | "profilePhoto">;

/**
 * `UserPatchRequest` (`PATCH /users/{id}`) — genuinely partial
 * (`exclude_unset`), unlike every other user-management-service PUT.
 * **Security note**: this route has no ownership check on the
 * backend (confirmed absent) — this feature only ever calls it with
 * the caller's own id from the live session, never an id a user could
 * type in, so it's used here strictly as a self-edit. See the
 * developer guide.
 */
export interface PatchUserIdentityInput {
  displayName?: string;
  firstName?: string;
  middleName?: string;
  lastName?: string;
  phoneNumber?: string;
}

// ---- Security (authentication-service) ----------------------------------------------

export interface MfaEnableResult {
  secret: string;
  otpauthUri: string;
  recoveryCodes: string[];
}

export interface ApiKeySummary {
  id: string;
  name: string;
  keyPrefix: string;
  scopes: string[];
  expiresAt: string | null;
  lastUsedAt: string | null;
  revokedAt: string | null;
}

/** Shown exactly once, immediately after creation — never retrievable
 * again (confirmed: `GET /auth/apikeys` never includes it). */
export interface ApiKeyCreated extends ApiKeySummary {
  rawKey: string;
}

export interface CreateApiKeyInput {
  name: string;
  scopes: string[];
  expiresInDays?: number;
}

export interface DeviceSummary {
  id: string;
  deviceName: string | null;
  browser: string | null;
  operatingSystem: string | null;
  ipAddress: string | null;
  location: string | null;
  lastLoginAt: string | null;
  isTrusted: boolean;
  trustedUntil: string | null;
}

export interface SessionSummary {
  id: string;
  sessionId: string;
  ipAddress: string | null;
  userAgent: string | null;
  createdAt: string;
  lastActiveAt: string;
  expiresAt: string;
}

// ---- Organization (organization-service) ---------------------------------------------

/** `OrganizationResponse`/`OrganizationUpdateRequest`
 * (`GET/PUT /organizations/{id}`). `PUT` resets every omitted field
 * to its schema default (confirmed: `OrganizationService.update`
 * overwrites unconditionally) — the form always resends the complete
 * object. No `version` field is exposed by this schema despite the
 * row carrying one internally (see the developer guide's Concurrency
 * section). */
export interface OrganizationIdentity {
  id: string;
  slug: string;
  name: string;
  displayName: string | null;
  shortName: string | null;
  description: string | null;
  status: string;
  primaryDomain: string | null;
  primaryContactEmail: string | null;
  logoUrl: string | null;
  website: string | null;
  industry: string | null;
  timezone: string;
  language: string;
  country: string | null;
  currency: string;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export type UpdateOrganizationIdentityInput = Omit<
  OrganizationIdentity,
  "id" | "slug" | "createdAt" | "updatedAt"
>;

/** `OrganizationSettingsResponse`/`...UpdateRequest`
 * (`GET/PUT /organizations/{id}/settings`) — real security/operational
 * policy fields, not branding. Same full-replace `PUT` semantics. */
export interface OrganizationSettings {
  passwordPolicy: Record<string, unknown>;
  mfaEnforced: boolean;
  allowedDomains: string[];
  defaultLanguage: string;
  defaultTimezone: string;
  sessionTimeoutMinutes: number;
  dataRetentionDays: number;
  storagePolicy: Record<string, unknown>;
  notificationPolicy: Record<string, unknown>;
}

export type UpdateOrganizationSettingsInput = OrganizationSettings;

/** `OrganizationBrandingResponse`/`...UpdateRequest`
 * (`GET/PUT /organizations/{id}/branding`). */
export interface OrganizationBranding {
  logoUrl: string | null;
  darkLogoUrl: string | null;
  faviconUrl: string | null;
  primaryColor: string | null;
  secondaryColor: string | null;
  theme: string;
  emailTemplates: Record<string, unknown>;
  loginScreenBranding: Record<string, unknown>;
  dashboardBranding: Record<string, unknown>;
}

export type UpdateOrganizationBrandingInput = OrganizationBranding;

/** `OrganizationLicenseResponse` (`GET /organizations/{id}/licenses`)
 * — shown read-only in this feature (see the developer guide's "Why
 * License/Quota are read-only here"). */
export interface OrganizationLicense {
  licenseType: string;
  seatCount: number;
  consumedSeats: number;
  status: string;
  expiresAt: string | null;
  gracePeriodDays: number;
  activatedAt: string | null;
}

/** `OrganizationQuotaResponse` (`GET /organizations/{id}/quotas`) —
 * read-only, same reasoning as License. */
export interface OrganizationQuota {
  maxUsers: number;
  maxProjects: number;
  maxAssets: number;
  maxStorageGb: number;
  maxWorkflows: number;
  maxAutomationJobs: number;
  maxConnectors: number;
  maxApiCallsPerDay: number;
  maxAiRequestsPerDay: number;
  maxPlugins: number;
}

// ---- Projects (project-service) -------------------------------------------------------

export const PROJECT_VISIBILITIES = ["private", "internal", "public"] as const;
export type ProjectVisibilityValue = (typeof PROJECT_VISIBILITIES)[number];

/** `ProjectResponse` (`GET /projects?organization_id=`, unbounded —
 * only ever used for the project picker, matching the same "unbounded,
 * picker-only" precedent as `assetsApi.listAll` — never a primary
 * list view). */
export interface ProjectSummary {
  id: string;
  organizationId: string;
  name: string;
  displayName: string | null;
  description: string | null;
  code: string | null;
  status: string;
  ownerId: string;
  visibility: string;
  defaultLanguage: string;
  timezone: string;
  category: string | null;
  priority: string;
  archivedAt: string | null;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

/** `ProjectPatchRequest` (`PATCH /projects/{id}`) — genuinely partial
 * (`exclude_unset`), unlike this service's own `PUT` counterpart. Used
 * exclusively over `PUT` for the same "PATCH, never PUT" reason
 * established in Prompt 011. */
export interface PatchProjectInput {
  name?: string;
  displayName?: string;
  description?: string;
  status?: string;
  visibility?: ProjectVisibilityValue;
  defaultLanguage?: string;
  timezone?: string;
  category?: string;
  priority?: string;
  metadata?: Record<string, unknown>;
}

/** `ProjectSettingsResponse`/`...UpdateRequest`
 * (`GET/PUT /projects/{id}/settings`) — full-replace `PUT` only, no
 * `PATCH` counterpart exists for this sub-resource (confirmed). Most
 * fields are opaque policy JSON blobs with no defined sub-schema
 * (`retentionPolicies`, `executionPolicies`, `automationPolicies`,
 * `validationPolicies`, `monitoringPolicies`, `aiSettings`,
 * `storagePolicies`, `securityPolicies`, `notificationSettings`) —
 * shown read-only/round-tripped unchanged, same reasoning as
 * `UserPreferences`'s own opaque fields; only the three well-typed
 * scalar fields are editable. */
export interface ProjectSettings {
  defaultEnvironment: string | null;
  defaultConnectorId: string | null;
  defaultWorkflowRuntime: string | null;
  notificationSettings: Record<string, unknown>;
  retentionPolicies: Record<string, unknown>;
  executionPolicies: Record<string, unknown>;
  automationPolicies: Record<string, unknown>;
  validationPolicies: Record<string, unknown>;
  monitoringPolicies: Record<string, unknown>;
  aiSettings: Record<string, unknown>;
  storagePolicies: Record<string, unknown>;
  securityPolicies: Record<string, unknown>;
}

export type UpdateProjectSettingsInput = ProjectSettings;

/**
 * `ProjectMemberResponse` (`GET /projects/{id}/members`, Prompt 014's
 * own research). Role is a real FK into a `project_roles` table, not
 * a free-text string — 8 seeded system codes, rank-ordered, no route
 * to discover them dynamically (see `PROJECT_ROLE_CODES` below).
 * Role is present directly on this response — no per-row extra
 * request needed.
 */
export interface ProjectMember {
  id: string;
  projectId: string;
  userId: string;
  roleId: string;
  roleCode: string;
  roleName: string;
  status: string;
  invitedBy: string | null;
  createdAt: string;
}

/** The 8 real, seeded system project-role codes (confirmed via the
 * seed migration — no endpoint lists them dynamically, so this is a
 * hardcoded but real, source-confirmed enum, the same treatment as
 * Prompt 013's connector categories). Rank order (highest first):
 * owner &gt; administrator &gt; {operator, automation_engineer,
 * validation_engineer} &gt; developer &gt; {viewer, auditor}. */
export const PROJECT_ROLE_CODES = [
  "owner",
  "administrator",
  "operator",
  "automation_engineer",
  "validation_engineer",
  "developer",
  "viewer",
  "auditor",
] as const;
export type ProjectRoleCodeValue = (typeof PROJECT_ROLE_CODES)[number];

export interface AddProjectMemberInput {
  userId: string;
  roleCode: ProjectRoleCodeValue;
}

/** Setting `roleCode: "owner"` is special-cased by the backend into a
 * full ownership transfer (the previous owner is demoted to
 * administrator, `project.ownerId` changes) — never treated as a
 * plain role edit in the UI; see `ProjectMembersSection`'s own
 * docstring. */
export interface UpdateProjectMemberRoleInput {
  roleCode: ProjectRoleCodeValue;
}

// ---- Integrations (integration-hub-service) --------------------------------------------

/** `ConnectorCategory` — the 15 real categories. No dedicated
 * "Ansible"/"Redfish"/"Kubernetes" category exists; those would be
 * free-text `connectorType` values under one of these (see the
 * developer guide's "Why no specialized Ansible/Kubernetes form"). */
export const CONNECTOR_CATEGORIES = [
  "cloud",
  "virtualization",
  "container_platforms",
  "monitoring",
  "itsm",
  "devops",
  "identity",
  "networking",
  "storage",
  "databases",
  "industrial_protocols",
  "messaging",
  "security",
  "business_applications",
  "custom",
] as const;
export type ConnectorCategoryValue = (typeof CONNECTOR_CATEGORIES)[number];

export const CONNECTOR_AUTH_METHODS = [
  "oauth2",
  "oidc",
  "api_key",
  "jwt",
  "basic",
  "bearer_token",
  "mutual_tls",
  "certificate",
  "username_password",
  "custom",
] as const;
export type ConnectorAuthMethodValue = (typeof CONNECTOR_AUTH_METHODS)[number];

/** `ConnectorLifecycleStatus` — real backend states. `enabled` is a
 * separate boolean flag, not one of these (a connector can be
 * `configured` and `enabled=false`, for example). */
export const CONNECTOR_LIFECYCLE_STATUSES = [
  "registered",
  "installed",
  "configured",
  "validated",
  "enabled",
  "disabled",
  "deprecated",
  "removed",
] as const;
export type ConnectorLifecycleStatusValue = (typeof CONNECTOR_LIFECYCLE_STATUSES)[number];

export interface Connector {
  id: string;
  organizationId: string;
  name: string;
  description: string | null;
  category: ConnectorCategoryValue;
  connectorType: string;
  status: ConnectorLifecycleStatusValue;
  authMethod: ConnectorAuthMethodValue;
  config: Record<string, unknown>;
  ownerId: string | null;
  enabled: boolean;
  consecutiveFailures: number;
  lastValidatedAt: string | null;
  lastHealthCheckAt: string | null;
  lastSyncAt: string | null;
  tags: string[];
  createdAt: string;
}

export interface CreateConnectorInput {
  organizationId: string;
  name: string;
  category: ConnectorCategoryValue;
  connectorType: string;
  authMethod?: ConnectorAuthMethodValue;
  description?: string;
  tags?: string[];
}

/** `ConnectorConfigureRequest` (`PUT /integrations/connectors/{id}`) —
 * a full replace of the whole `config` dict (confirmed: no PATCH
 * exists for this route), moves the connector to `configured`. */
export interface ConfigureConnectorInput {
  config: Record<string, unknown>;
}

export const CONNECTION_TEST_STATUSES = ["success", "failed"] as const;
export type ConnectionTestStatusValue = (typeof CONNECTION_TEST_STATUSES)[number];

/** `ConnectionTestResponse` (`POST /integrations/connectors/{id}/test`).
 * `status === "success"` with no `latencyMs` means a structural check
 * only (config+credential presence, no real outbound call) — see the
 * developer guide. */
export interface ConnectionTestResult {
  id: string;
  connectorId: string;
  credentialId: string | null;
  status: ConnectionTestStatusValue;
  testedAt: string;
  latencyMs: number | null;
  error: string | null;
  attemptNumber: number;
}

/** `CredentialResponse` — never includes the secret value itself
 * (confirmed: no such field exists on this response schema at all,
 * not even masked). */
export interface ConnectorCredential {
  id: string;
  connectorId: string;
  credentialType: string;
  status: string;
  secretRef: string | null;
  expiresAt: string | null;
  lastValidatedAt: string | null;
  lastRotatedAt: string | null;
  createdAt: string;
}

export interface AssignCredentialInput {
  connectorId: string;
  credentialType: string;
  secretRef?: string;
  rawValue?: string;
  refreshValue?: string;
  expiresAt?: string;
}

// ---- Notifications (notification-center-service) --------------------------------------

export const NOTIFICATION_CHANNEL_KINDS = [
  "email",
  "sms",
  "slack",
  "teams",
  "discord",
  "webhook",
  "mobile_push",
  "browser_push",
  "in_app",
  "rest_callback",
  "custom",
] as const;
export type NotificationChannelKindValue = (typeof NOTIFICATION_CHANNEL_KINDS)[number];

export const NOTIFICATION_CATEGORIES = [
  "alert",
  "warning",
  "information",
  "success",
  "failure",
  "critical",
  "reminder",
  "approval_request",
  "assignment",
  "system_announcement",
  "maintenance_notice",
  "digest",
  "custom",
] as const;
export type NotificationCategoryValue = (typeof NOTIFICATION_CATEGORIES)[number];

export const DIGEST_FREQUENCIES = ["none", "hourly", "daily", "weekly", "monthly"] as const;
export type DigestFrequencyValue = (typeof DIGEST_FREQUENCIES)[number];

/** `PreferenceResponse` (`GET/PUT /notifications/preferences?organization_id=`).
 * Unlike every user-management-service PUT, this one is genuinely
 * partial-safe — confirmed: `PreferenceService.update` only applies a
 * field when it's present and non-null. `deviceTokens`/
 * `priorityOverrides` are round-tripped unchanged (opaque/advanced,
 * no form control built for them). */
export interface NotificationPreferences {
  id: string;
  organizationId: string;
  userId: string;
  preferredChannels: NotificationChannelKindValue[];
  mutedCategories: NotificationCategoryValue[];
  unsubscribedChannels: NotificationChannelKindValue[];
  channelPriority: NotificationChannelKindValue[];
  deviceTokens: string[];
  quietHoursStart: string | null;
  quietHoursEnd: string | null;
  language: string | null;
  timezone: string | null;
  digestFrequency: DigestFrequencyValue;
  muted: boolean;
  priorityOverrides: Record<string, unknown>;
}

export type UpdateNotificationPreferencesInput = Omit<NotificationPreferences, "id" | "organizationId" | "userId">;

/** `ChannelConfigResponse` (`GET/PUT /notifications/channels/{channel}`)
 * — organization-level channel configuration (e.g. a Slack webhook
 * URL), not a personal preference. **Security note**: the backend
 * echoes `config` back completely unmasked, with no redaction of
 * secret-shaped values (confirmed absent) — this frontend masks any
 * key that looks credential-like in the presentation layer only, the
 * same defensive heuristic Prompt 011 established, since the backend
 * itself provides none. */
export interface NotificationChannelConfig {
  id: string;
  organizationId: string;
  channel: NotificationChannelKindValue;
  enabled: boolean;
  config: Record<string, unknown>;
  description: string | null;
}

export interface UpdateNotificationChannelInput {
  enabled: boolean;
  config: Record<string, unknown>;
  description?: string;
}

// ---- System (administration-portal-service) --------------------------------------------

/** `DashboardResponse` (`GET /admin/dashboard`) — read-only. */
export interface AdminDashboardSnapshot {
  tenantCount: number;
  activeTenantCount: number;
  organizationCount: number;
  runningJobCount: number;
  failedJobCount: number;
  openMaintenanceWindowCount: number;
  overallHealth: string;
}

/** `SettingResponse`/`SettingUpsertRequest` (`GET/PUT /admin/settings`)
 * — a flat key/value(+description) store, `value` is an arbitrary
 * JSON-compatible value, not a typed schema. No `version` field. */
export interface PlatformSetting {
  id: string;
  key: string;
  value: unknown;
  description: string | null;
}

export interface UpsertPlatformSettingInput {
  key: string;
  value: unknown;
  description?: string;
}

/** `FeatureFlagResponse` (`GET/POST /admin/feature-flags`,
 * `PUT /admin/feature-flags/{id}`). Richer than a plain boolean:
 * `isKilled` is a separate emergency kill-switch from `isEnabled`, and
 * `rolloutPercentage` is a real gradual-rollout float, not fabricated. */
export interface FeatureFlag {
  id: string;
  name: string;
  scope: string;
  targetRef: string | null;
  rolloutPercentage: number;
  isEnabled: boolean;
  isKilled: boolean;
}

export interface CreateFeatureFlagInput {
  name: string;
  scope: string;
  targetRef?: string;
  rolloutPercentage?: number;
}

/** All optional — `PUT` here is genuinely partial (confirmed:
 * `FeatureFlagUpdateRequest`'s own fields are all `Optional`). */
export interface UpdateFeatureFlagInput {
  isEnabled?: boolean;
  isKilled?: boolean;
  rolloutPercentage?: number;
}

/** `JobResponse` (`GET/POST /admin/jobs`) — enqueue + read-only list
 * only; no route cancels, retries, or transitions a job (confirmed
 * absent). */
export interface SystemJob {
  id: string;
  jobKey: string;
  status: string;
  priority: string;
  attemptCount: number;
  maxAttempts: number;
  queuedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface EnqueueSystemJobInput {
  jobKey: string;
  priority?: string;
  payload?: Record<string, unknown>;
  maxAttempts?: number;
}

/** `DiagnosticResponse` (`GET /admin/diagnostics`) — read-only. */
export interface DiagnosticEntry {
  id: string;
  category: string;
  status: string;
  latencyMs: number | null;
  ranAt: string;
}

/** `PlatformHealthResponse` (`GET /admin/health`) — read-only. */
export interface PlatformHealth {
  overallStatus: string;
  components: { component: string; status: string; checkedAt: string }[];
}

/** `StatisticWindowResponse` (`GET /admin/statistics`) — read-only. */
export interface StatisticWindow {
  windowStart: string;
  windowEnd: string;
  tenantCount: number;
  userCount: number;
  apiRequestCount: number;
  backgroundJobCount: number;
  securityEventCount: number;
  platformAvailabilityFraction: number;
}

/** `ReportResponse` (`GET /admin/reports`) — metadata only, no
 * content/download field exists on this response (confirmed absent). */
export interface AdminReportMeta {
  id: string;
  kind: string;
  reportFormat: string;
  title: string;
  status: string;
  periodStart: string;
  periodEnd: string;
  generatedAt: string | null;
  rowCount: number | null;
}
