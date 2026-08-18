/**
 * Types mirroring the real V1 responses this feature consumes, confirmed
 * by direct source inspection of `services/reporting-service` — enums
 * from `app/models/enums.py`, request/response shapes from
 * `app/schemas/report.py`, `app/schemas/template.py`,
 * `app/schemas/delivery.py`, and the designer document from
 * `app/reports/designer/schema.py`. See
 * `docs/frontend/developer-guide/reporting.md` for the endpoint each one
 * comes from.
 */

export const REPORT_CATEGORIES = [
  "infrastructure",
  "inventory",
  "discovery",
  "configuration",
  "automation",
  "workflow",
  "validation",
  "monitoring",
  "alerting",
  "compliance",
  "security",
  "incident",
  "capacity",
  "availability",
  "performance",
  "executive",
  "operational",
  "financial",
  "custom",
] as const;
export type ReportCategory = (typeof REPORT_CATEGORIES)[number];

export const REPORT_TYPES = [
  "tabular",
  "summary",
  "executive",
  "trend",
  "historical",
  "comparison",
  "compliance",
  "analytical",
  "dashboard_export",
  "ai_summary",
  "custom",
] as const;
export type ReportTypeValue = (typeof REPORT_TYPES)[number];

export const EXPORT_FORMATS = ["pdf", "xlsx", "csv", "json", "markdown", "html", "xml"] as const;
export type ExportFormat = (typeof EXPORT_FORMATS)[number];

export const DATA_SOURCES = [
  "inventory",
  "discovery",
  "configuration",
  "automation",
  "workflow",
  "validation",
  "monitoring",
  "alerting",
  "ai_assistant",
  "compliance",
  "incident",
  "administration",
  "custom_api",
] as const;
export type DataSourceValue = (typeof DATA_SOURCES)[number];

export const REPORT_EXECUTION_STATUSES = ["pending", "running", "succeeded", "failed", "cancelled"] as const;
export type ReportExecutionStatusValue = (typeof REPORT_EXECUTION_STATUSES)[number];

export const SCHEDULE_FREQUENCIES = ["one_time", "hourly", "daily", "weekly", "monthly", "cron"] as const;
export type ScheduleFrequencyValue = (typeof SCHEDULE_FREQUENCIES)[number];

export const DISTRIBUTION_CHANNELS = ["download", "email", "webhook", "shared_link", "api", "object_storage"] as const;
export type DistributionChannelValue = (typeof DISTRIBUTION_CHANNELS)[number];

export const DISTRIBUTION_STATUSES = ["pending", "delivered", "failed", "expired"] as const;
export type DistributionStatusValue = (typeof DISTRIBUTION_STATUSES)[number];

export const TEMPLATE_STATUSES = ["draft", "approved", "archived"] as const;
export type TemplateStatusValue = (typeof TEMPLATE_STATUSES)[number];

export const SECTION_KINDS = ["heading", "text", "table", "chart", "metric", "ai_summary", "page_break"] as const;
export type SectionKindValue = (typeof SECTION_KINDS)[number];

export const CHART_KINDS = ["bar", "line", "pie"] as const;
export type ChartKindValue = (typeof CHART_KINDS)[number];

export const PARAMETER_KINDS = ["string", "integer", "number", "boolean", "date", "datetime", "uuid", "enum"] as const;
export type ParameterKindValue = (typeof PARAMETER_KINDS)[number];

export const FILTER_OPERATORS = [
  "eq",
  "ne",
  "gt",
  "gte",
  "lt",
  "lte",
  "in",
  "not_in",
  "contains",
  "starts_with",
  "between",
  "is_null",
  "is_not_null",
] as const;
export type FilterOperatorValue = (typeof FILTER_OPERATORS)[number];

export const ARCHIVE_STATUSES = ["active", "restored", "purged"] as const;
export type ArchiveStatusValue = (typeof ARCHIVE_STATUSES)[number];

/** A saved report's own `filters` field and `POST /reports/generate`'s
 * `filters` override share this clause shape (`app/filters/engine.py#FilterClause`).
 * `value` is absent/ignored for `is_null`/`is_not_null`. */
export interface FilterClause {
  field: string;
  operator: FilterOperatorValue;
  value?: unknown;
}

/** `ReportResponse` — `GET/PUT /reports/{id}`, `GET /reports`. No
 * status/version/timestamps are exposed even though the underlying row
 * has them — see `backend-v1-integration-limitations.md`. */
export interface Report {
  id: string;
  organizationId: string;
  projectId: string | null;
  templateId: string | null;
  name: string;
  description: string | null;
  category: ReportCategory;
  reportType: ReportTypeValue;
  defaultFormat: ExportFormat;
  parameterValues: Record<string, unknown>;
  filters: FilterClause[];
  enabled: boolean;
  ownerId: string | null;
}

export interface ReportCreateInput {
  organizationId: string;
  projectId?: string;
  name: string;
  description?: string;
  category: ReportCategory;
  reportType: ReportTypeValue;
  templateId?: string;
  defaultFormat?: ExportFormat;
  parameterValues?: Record<string, unknown>;
  filters?: FilterClause[];
}

/** Every field optional — a partial update; omitting a field leaves it
 * alone rather than clearing it (`ReportUpdateRequest`'s own docstring). */
export interface ReportUpdateInput {
  name?: string;
  description?: string;
  defaultFormat?: ExportFormat;
  parameterValues?: Record<string, unknown>;
  filters?: FilterClause[];
  enabled?: boolean;
}

/** `ExportSummary` — deliberately excludes the artifact's bytes; fetch
 * those via the dedicated download endpoint. */
export interface ExportArtifact {
  id: string;
  executionId: string;
  exportFormat: ExportFormat;
  filename: string;
  contentType: string;
  sizeBytes: number;
  checksumSha256: string;
  downloadCount: number;
}

/** `ExecutionResponse` — one generation run. */
export interface ReportExecution {
  id: string;
  jobId: string;
  scheduleId: string | null;
  status: ReportExecutionStatusValue;
  rowCount: number;
  sectionCount: number;
  durationMs: number | null;
  errorMessage: string | null;
  triggeredBy: string | null;
  startedAt: string | null;
  finishedAt: string | null;
}

/** `GenerateResponse` — `POST /reports/generate` is synchronous; this
 * is the complete result of one run, not a job handle to poll. */
export interface GenerateResult {
  execution: ReportExecution;
  exports: ExportArtifact[];
  degradedSections: string[];
  distributions: string[];
  archiveId: string | null;
}

export interface GenerateInput {
  reportId: string;
  exportFormats?: ExportFormat[];
  parameterValues?: Record<string, unknown>;
  filters?: FilterClause[];
  distribute?: boolean;
  archive?: boolean;
  signedBy?: string;
  pdfPassword?: string;
}

/** `HistoryResponse` — `GET /reports/history`, the user-visible
 * activity feed. Distinct from the write-only security audit trail
 * (`ReportAudit`), which has no GET endpoint at all. */
export interface ReportHistoryEntry {
  id: string;
  jobId: string;
  executionId: string | null;
  event: string;
  summary: string;
  details: Record<string, unknown>;
  actorId: string | null;
  occurredAt: string;
}

/** `StatisticsResponse` — `GET /reports/statistics`. The five `*_usage`/
 * `popular_reports` fields are plain `dict[str, Any]` (built via
 * Python's `Counter`) — typed as `Record<string, number>`, never
 * assumed to have a richer per-entry shape. */
export interface ReportingStatistics {
  totalReports: number;
  totalExecutions: number;
  successfulExecutions: number;
  failedExecutions: number;
  scheduledExecutions: number;
  totalDownloads: number;
  totalDistributions: number;
  failedDistributions: number;
  averageDurationMs: number;
  popularReports: Record<string, number>;
  exportFormatUsage: Record<string, number>;
  templateUsage: Record<string, number>;
  scheduleUsage: Record<string, number>;
  distributionUsage: Record<string, number>;
  computedAt: string;
}

// ---- Designer document (a template's `definition`) -------------------

export interface DataQuery {
  source: DataSourceValue;
  path: string;
  params?: Record<string, unknown>;
  resultPath?: string;
}

export interface ColumnSpec {
  key: string;
  label: string;
  width?: number;
  /** `date | datetime | percent | bytes | number` are the documented
   * formatters — any other value is accepted server-side and simply
   * falls back to a plain string, not rejected. */
  format?: string;
}

export interface ChartSpec {
  kind: ChartKindValue;
  labelKey: string;
  valueKey: string;
  title?: string;
  maxSlices?: number;
}

export type MetricAggregate = "count" | "sum" | "avg" | "min" | "max";

export interface ReportSection {
  key: string;
  kind: SectionKindValue;
  title?: string;
  text?: string;
  query?: DataQuery;
  columns?: ColumnSpec[];
  chart?: ChartSpec;
  metricKey?: string;
  metricAggregate?: MetricAggregate;
  aiPrompt?: string;
}

export interface Branding {
  companyName?: string;
  logoDataUri?: string;
  theme?: string;
  footerText?: string;
  showPageNumbers?: boolean;
  showTableOfContents?: boolean;
}

export interface ReportDefinition {
  title: string;
  subtitle?: string;
  sections: ReportSection[];
  branding?: Branding;
}

// ---- Templates ---------------------------------------------------------

export interface ParameterDeclaration {
  key: string;
  label: string;
  description?: string;
  kind: ParameterKindValue;
  required: boolean;
  defaultValue?: unknown;
  allowedValues: unknown[];
  displayOrder: number;
}

/** `TemplateResponse` — one version of a template. `id` identifies this
 * specific version row; `name` is shared across a template's versions. */
export interface ReportTemplate {
  id: string;
  organizationId: string;
  projectId: string | null;
  categoryId: string | null;
  name: string;
  description: string | null;
  category: ReportCategory;
  reportType: ReportTypeValue;
  versionNumber: string;
  status: TemplateStatusValue;
  definition: ReportDefinition;
  branding: Record<string, unknown>;
  isSystem: boolean;
  approvedBy: string | null;
  approvedAt: string | null;
}

export interface TemplateCreateInput {
  organizationId: string;
  projectId?: string;
  name: string;
  description?: string;
  category: ReportCategory;
  reportType: ReportTypeValue;
  categoryId?: string;
  definition: ReportDefinition;
  branding?: Record<string, unknown>;
  parameters?: ParameterDeclaration[];
}

export interface TemplateVersionInput {
  definition: ReportDefinition;
  branding?: Record<string, unknown>;
  parameters?: ParameterDeclaration[];
}

/** `CategoryResponse` — org-owned display metadata layered over the
 * fixed `ReportCategory` enum (name/slug/ordering), not a replacement
 * for it. */
export interface ReportCategoryRecord {
  id: string;
  organizationId: string;
  category: ReportCategory;
  slug: string;
  name: string;
  description: string | null;
  displayOrder: number;
  enabled: boolean;
}

export interface CategoryCreateInput {
  organizationId: string;
  projectId?: string;
  category: ReportCategory;
  slug: string;
  name: string;
  description?: string;
  displayOrder?: number;
}

// ---- Scheduling ----------------------------------------------------------

export interface ReportSchedule {
  id: string;
  jobId: string;
  frequency: ScheduleFrequencyValue;
  cronExpression: string | null;
  timezone: string;
  exportFormat: ExportFormat;
  startsAt: string;
  endsAt: string | null;
  nextRunAt: string | null;
  lastRunAt: string | null;
  maxRetries: number;
  consecutiveFailures: number;
  notifyOnFailure: boolean;
  lastError: string | null;
  enabled: boolean;
}

export interface ScheduleCreateInput {
  organizationId: string;
  projectId?: string;
  reportId: string;
  frequency: ScheduleFrequencyValue;
  startsAt: string;
  endsAt?: string;
  cronExpression?: string;
  timezone?: string;
  exportFormat?: ExportFormat;
  maxRetries?: number;
  notifyOnFailure?: boolean;
}

/** `starts_at` cannot be changed once a schedule exists (confirmed by
 * source inspection — absent from `ScheduleUpdateRequest`). */
export interface ScheduleUpdateInput {
  frequency?: ScheduleFrequencyValue;
  cronExpression?: string;
  timezone?: string;
  exportFormat?: ExportFormat;
  endsAt?: string;
  enabled?: boolean;
}

// ---- Distribution / sharing ----------------------------------------------

export interface ReportRecipient {
  id: string;
  jobId: string;
  channel: DistributionChannelValue;
  target: string;
  exportFormat: ExportFormat;
  headers: Record<string, string>;
  enabled: boolean;
}

export interface RecipientCreateInput {
  organizationId: string;
  projectId?: string;
  channel: DistributionChannelValue;
  target: string;
  exportFormat?: ExportFormat;
  headers?: Record<string, string>;
}

/** `DistributionResponse` — `share_token` is deliberately never
 * included here (returned exactly once, by `ShareLinkResponse`, at
 * creation). */
export interface ReportDistribution {
  id: string;
  exportId: string;
  recipientId: string | null;
  channel: DistributionChannelValue;
  target: string;
  status: DistributionStatusValue;
  attempts: number;
  expiresAt: string | null;
  storageUri: string | null;
  errorMessage: string | null;
  deliveredAt: string | null;
}

export interface DistributeInput {
  channel: DistributionChannelValue;
  target?: string;
  headers?: Record<string, string>;
}

/** `ShareLinkResponse` — the token is shown to the caller exactly once.
 * There is no revoke endpoint; a link is only invalidated by its own
 * `expiresAt`. */
export interface ShareLink {
  distributionId: string;
  shareToken: string;
  expiresAt: string | null;
}

// ---- Archive ---------------------------------------------------------------

export interface ArchivedReport {
  id: string;
  executionId: string | null;
  jobId: string | null;
  title: string;
  exportFormat: ExportFormat;
  filename: string;
  contentType: string;
  sizeBytes: number;
  checksumSha256: string;
  archiveVersion: number;
  status: ArchiveStatusValue;
  archivedAt: string;
  retentionUntil: string | null;
  purgeReason: string | null;
}

export interface ArchiveCreateInput {
  exportId: string;
  title: string;
  retentionDays?: number;
}
