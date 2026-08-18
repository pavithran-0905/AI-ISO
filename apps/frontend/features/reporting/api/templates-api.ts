/**
 * `services/reporting-service/app/api/templates.py` — confirmed by
 * source inspection. A template's `definition` (the designer document)
 * is validated server-side against `ReportDefinition` on every write;
 * there is no separate "configure sections" endpoint — the whole
 * document is replaced atomically per version via
 * `POST /reports/templates/{id}/versions`.
 */

import { apiClient } from "@/api/client";
import type {
  Branding,
  CategoryCreateInput,
  ChartKindValue,
  ChartSpec,
  ColumnSpec,
  DataQuery,
  DataSourceValue,
  MetricAggregate,
  ParameterDeclaration,
  ParameterKindValue,
  ReportCategory,
  ReportCategoryRecord,
  ReportDefinition,
  ReportSection,
  ReportTemplate,
  ReportTypeValue,
  SectionKindValue,
  TemplateCreateInput,
  TemplateStatusValue,
  TemplateVersionInput,
} from "@/features/reporting/types";

interface ParameterDeclarationBody {
  key: string;
  label: string;
  description?: string | null;
  kind?: ParameterKindValue;
  required?: boolean;
  default_value?: unknown;
  allowed_values?: unknown[];
  display_order?: number;
}

interface DataQueryBody {
  source: DataSourceValue;
  path: string;
  params?: Record<string, unknown>;
  result_path?: string | null;
}

interface ColumnSpecBody {
  key: string;
  label: string;
  width?: number | null;
  format?: string | null;
}

interface ChartSpecBody {
  kind?: ChartKindValue;
  label_key: string;
  value_key: string;
  title?: string | null;
  max_slices?: number;
}

interface ReportSectionBody {
  key: string;
  kind: SectionKindValue;
  title?: string | null;
  text?: string | null;
  query?: DataQueryBody | null;
  columns?: ColumnSpecBody[];
  chart?: ChartSpecBody | null;
  metric_key?: string | null;
  metric_aggregate?: MetricAggregate;
  ai_prompt?: string | null;
}

interface BrandingBody {
  company_name?: string;
  logo_data_uri?: string | null;
  theme?: string;
  footer_text?: string | null;
  show_page_numbers?: boolean;
  show_table_of_contents?: boolean;
}

interface ReportDefinitionBody {
  title: string;
  subtitle?: string | null;
  sections: ReportSectionBody[];
  branding?: BrandingBody;
}

interface TemplateResponseBody {
  id: string;
  organization_id: string;
  project_id: string | null;
  category_id: string | null;
  name: string;
  description: string | null;
  category: ReportCategory;
  report_type: ReportTypeValue;
  version_number: string;
  status: TemplateStatusValue;
  definition: ReportDefinitionBody;
  branding: Record<string, unknown>;
  is_system: boolean;
  approved_by: string | null;
  approved_at: string | null;
}

interface ParameterResponseBody {
  id: string;
  template_id: string;
  key: string;
  label: string;
  description: string | null;
  kind: ParameterKindValue;
  required: boolean;
  default_value: unknown;
  allowed_values: unknown[];
  display_order: number;
}

interface CategoryResponseBody {
  id: string;
  organization_id: string;
  category: ReportCategory;
  slug: string;
  name: string;
  description: string | null;
  display_order: number;
  enabled: boolean;
}

function toDataQuery(body: DataQueryBody): DataQuery {
  return { source: body.source, path: body.path, params: body.params, resultPath: body.result_path ?? undefined };
}

function fromDataQuery(query: DataQuery): DataQueryBody {
  return { source: query.source, path: query.path, params: query.params, result_path: query.resultPath };
}

function toColumn(body: ColumnSpecBody): ColumnSpec {
  return { key: body.key, label: body.label, width: body.width ?? undefined, format: body.format ?? undefined };
}

function fromColumn(column: ColumnSpec): ColumnSpecBody {
  return { key: column.key, label: column.label, width: column.width, format: column.format };
}

function toChart(body: ChartSpecBody): ChartSpec {
  return {
    kind: body.kind ?? "bar",
    labelKey: body.label_key,
    valueKey: body.value_key,
    title: body.title ?? undefined,
    maxSlices: body.max_slices,
  };
}

function fromChart(chart: ChartSpec): ChartSpecBody {
  return { kind: chart.kind, label_key: chart.labelKey, value_key: chart.valueKey, title: chart.title, max_slices: chart.maxSlices };
}

function toSection(body: ReportSectionBody): ReportSection {
  return {
    key: body.key,
    kind: body.kind,
    title: body.title ?? undefined,
    text: body.text ?? undefined,
    query: body.query ? toDataQuery(body.query) : undefined,
    columns: body.columns?.map(toColumn) ?? [],
    chart: body.chart ? toChart(body.chart) : undefined,
    metricKey: body.metric_key ?? undefined,
    metricAggregate: body.metric_aggregate ?? "count",
    aiPrompt: body.ai_prompt ?? undefined,
  };
}

function fromSection(section: ReportSection): ReportSectionBody {
  return {
    key: section.key,
    kind: section.kind,
    title: section.title,
    text: section.text,
    query: section.query ? fromDataQuery(section.query) : undefined,
    columns: section.columns?.map(fromColumn) ?? [],
    chart: section.chart ? fromChart(section.chart) : undefined,
    metric_key: section.metricKey,
    metric_aggregate: section.metricAggregate,
    ai_prompt: section.aiPrompt,
  };
}

function toBranding(body?: BrandingBody): Branding {
  return {
    companyName: body?.company_name,
    logoDataUri: body?.logo_data_uri ?? undefined,
    theme: body?.theme,
    footerText: body?.footer_text ?? undefined,
    showPageNumbers: body?.show_page_numbers,
    showTableOfContents: body?.show_table_of_contents,
  };
}

function fromBranding(branding?: Branding): BrandingBody | undefined {
  if (!branding) return undefined;
  return {
    company_name: branding.companyName,
    logo_data_uri: branding.logoDataUri,
    theme: branding.theme,
    footer_text: branding.footerText,
    show_page_numbers: branding.showPageNumbers,
    show_table_of_contents: branding.showTableOfContents,
  };
}

function toDefinition(body: ReportDefinitionBody): ReportDefinition {
  return {
    title: body.title,
    subtitle: body.subtitle ?? undefined,
    sections: body.sections.map(toSection),
    branding: toBranding(body.branding),
  };
}

function fromDefinition(definition: ReportDefinition): ReportDefinitionBody {
  return {
    title: definition.title,
    subtitle: definition.subtitle,
    sections: definition.sections.map(fromSection),
    branding: fromBranding(definition.branding),
  };
}

function toParameterDeclarationBody(param: ParameterDeclaration): ParameterDeclarationBody {
  return {
    key: param.key,
    label: param.label,
    description: param.description,
    kind: param.kind,
    required: param.required,
    default_value: param.defaultValue,
    allowed_values: param.allowedValues,
    display_order: param.displayOrder,
  };
}

function toTemplate(body: TemplateResponseBody): ReportTemplate {
  return {
    id: body.id,
    organizationId: body.organization_id,
    projectId: body.project_id,
    categoryId: body.category_id,
    name: body.name,
    description: body.description,
    category: body.category,
    reportType: body.report_type,
    versionNumber: body.version_number,
    status: body.status,
    definition: toDefinition(body.definition),
    branding: body.branding,
    isSystem: body.is_system,
    approvedBy: body.approved_by,
    approvedAt: body.approved_at,
  };
}

function toParameter(body: ParameterResponseBody): ParameterDeclaration {
  return {
    key: body.key,
    label: body.label,
    description: body.description ?? undefined,
    kind: body.kind,
    required: body.required,
    defaultValue: body.default_value,
    allowedValues: body.allowed_values,
    displayOrder: body.display_order,
  };
}

function toCategoryRecord(body: CategoryResponseBody): ReportCategoryRecord {
  return {
    id: body.id,
    organizationId: body.organization_id,
    category: body.category,
    slug: body.slug,
    name: body.name,
    description: body.description,
    displayOrder: body.display_order,
    enabled: body.enabled,
  };
}

export const templatesApi = {
  async list(organizationId: string, category?: ReportCategory): Promise<ReportTemplate[]> {
    const query = new URLSearchParams({ organization_id: organizationId });
    if (category) query.set("category", category);
    const body = await apiClient.get<TemplateResponseBody[]>(`/reports/templates?${query.toString()}`);
    return body.map(toTemplate);
  },

  async getById(id: string): Promise<ReportTemplate> {
    const body = await apiClient.get<TemplateResponseBody>(`/reports/templates/${encodeURIComponent(id)}`);
    return toTemplate(body);
  },

  async listParameters(templateId: string): Promise<ParameterDeclaration[]> {
    const body = await apiClient.get<ParameterResponseBody[]>(`/reports/templates/${encodeURIComponent(templateId)}/parameters`);
    return body.map(toParameter);
  },

  /** Every version of the template that shares this template's `name`
   * — not this one version's own history. */
  async listVersions(templateId: string): Promise<ReportTemplate[]> {
    const body = await apiClient.get<TemplateResponseBody[]>(`/reports/templates/${encodeURIComponent(templateId)}/versions`);
    return body.map(toTemplate);
  },

  async create(input: TemplateCreateInput): Promise<ReportTemplate> {
    const body = await apiClient.post<TemplateResponseBody>("/reports/templates", {
      organization_id: input.organizationId,
      project_id: input.projectId,
      name: input.name,
      description: input.description,
      category: input.category,
      report_type: input.reportType,
      category_id: input.categoryId,
      definition: fromDefinition(input.definition),
      branding: input.branding,
      parameters: input.parameters?.map(toParameterDeclarationBody),
    });
    return toTemplate(body);
  },

  /** Adds a new `draft`, minor-bumped version — never edits an existing
   * version's `definition` in place. */
  async addVersion(templateId: string, input: TemplateVersionInput): Promise<ReportTemplate> {
    const body = await apiClient.post<TemplateResponseBody>(`/reports/templates/${encodeURIComponent(templateId)}/versions`, {
      definition: fromDefinition(input.definition),
      branding: input.branding,
      parameters: input.parameters?.map(toParameterDeclarationBody),
    });
    return toTemplate(body);
  },

  async approve(templateId: string): Promise<ReportTemplate> {
    const body = await apiClient.post<TemplateResponseBody>(`/reports/templates/${encodeURIComponent(templateId)}/approve`);
    return toTemplate(body);
  },

  async archive(templateId: string): Promise<ReportTemplate> {
    const body = await apiClient.post<TemplateResponseBody>(`/reports/templates/${encodeURIComponent(templateId)}/archive`);
    return toTemplate(body);
  },

  async listCategories(organizationId: string): Promise<ReportCategoryRecord[]> {
    const body = await apiClient.get<CategoryResponseBody[]>(`/reports/categories?organization_id=${encodeURIComponent(organizationId)}`);
    return body.map(toCategoryRecord);
  },

  async createCategory(input: CategoryCreateInput): Promise<ReportCategoryRecord> {
    const body = await apiClient.post<CategoryResponseBody>("/reports/categories", {
      organization_id: input.organizationId,
      project_id: input.projectId,
      category: input.category,
      slug: input.slug,
      name: input.name,
      description: input.description,
      display_order: input.displayOrder,
    });
    return toCategoryRecord(body);
  },
};
