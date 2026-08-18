"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import { CHART_KINDS, DATA_SOURCES, SECTION_KINDS, type ChartKindValue, type ColumnSpec, type DataSourceValue, type MetricAggregate, type ReportSection, type SectionKindValue } from "@/features/reporting/types";

const METRIC_AGGREGATES: MetricAggregate[] = ["count", "sum", "avg", "min", "max"];

function emptySection(): ReportSection {
  return { key: "", kind: "text", columns: [], metricAggregate: "count" };
}

/**
 * One designer section (§7/§8) — the input set follows the section's
 * own `kind`, matching the real per-kind requirements the backend
 * validates on write (`ReportSection._validate_kind_requirements`):
 * a table needs a query and columns, a chart needs a query and a chart
 * spec, a metric needs a query, heading/text need text. This dialog
 * enforces the same requirements client-side so a save attempt fails
 * here with a clear message rather than as an opaque 400 from the API.
 *
 * The caller must pass a `key` that changes between "add a new
 * section" and "edit section X" (e.g. `key={section?.key ?? "new"}`)
 * so this component remounts with a fresh draft instead of carrying
 * stale state between different sections — deliberately not
 * re-derived from props internally, to keep the reset unambiguous.
 */
export function SectionFormDialog({
  section,
  open,
  onClose,
  onSave,
}: {
  section: ReportSection | null;
  open: boolean;
  onClose: () => void;
  onSave: (section: ReportSection) => void;
}) {
  const [draft, setDraft] = useState<ReportSection>(section ?? emptySection());
  const [error, setError] = useState<string | null>(null);

  function validate(): string | null {
    if (!draft.key.trim()) return "A section key is required.";
    if ((draft.kind === "heading" || draft.kind === "text") && !draft.text?.trim()) return "This section kind requires text.";
    if (draft.kind === "table" && (!draft.query || (draft.columns ?? []).length === 0)) return "A table section requires a query and at least one column.";
    if (draft.kind === "chart" && (!draft.query || !draft.chart)) return "A chart section requires a query and chart settings.";
    if (draft.kind === "metric" && !draft.query) return "A metric section requires a query.";
    return null;
  }

  function handleSave() {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    onSave(draft);
    onClose();
  }

  function updateColumn(index: number, patch: Partial<ColumnSpec>) {
    setDraft((current) => ({ ...current, columns: (current.columns ?? []).map((column, i) => (i === index ? { ...column, ...patch } : column)) }));
  }

  function addColumn() {
    setDraft((current) => ({ ...current, columns: [...(current.columns ?? []), { key: "", label: "" }] }));
  }

  function removeColumn(index: number) {
    setDraft((current) => ({ ...current, columns: (current.columns ?? []).filter((_, i) => i !== index) }));
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={section ? "Edit section" : "Add section"}
      className="max-w-lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save section</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="section-key">Key</Label>
            <Input id="section-key" value={draft.key} onChange={(event) => setDraft({ ...draft, key: event.target.value })} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="section-kind">Kind</Label>
            <Select id="section-kind" value={draft.kind} onChange={(event) => setDraft({ ...draft, kind: event.target.value as SectionKindValue })}>
              {SECTION_KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {kind.replace("_", " ")}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="section-title">Title (optional)</Label>
          <Input id="section-title" value={draft.title ?? ""} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
        </div>

        {(draft.kind === "heading" || draft.kind === "text") && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="section-text">Text (static prose or Jinja2)</Label>
            <Textarea id="section-text" value={draft.text ?? ""} onChange={(event) => setDraft({ ...draft, text: event.target.value })} />
          </div>
        )}

        {draft.kind === "ai_summary" && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="section-ai-prompt">AI prompt</Label>
            <Textarea id="section-ai-prompt" value={draft.aiPrompt ?? ""} onChange={(event) => setDraft({ ...draft, aiPrompt: event.target.value })} />
          </div>
        )}

        {(draft.kind === "table" || draft.kind === "chart" || draft.kind === "metric") && (
          <div className="border-border flex flex-col gap-3 rounded-md border p-3">
            <p className="text-sm font-medium">Data query</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="section-query-source">Source</Label>
                <Select
                  id="section-query-source"
                  value={draft.query?.source ?? ""}
                  onChange={(event) => setDraft({ ...draft, query: { ...(draft.query ?? { path: "" }), source: event.target.value as DataSourceValue } })}
                >
                  <option value="">Select…</option>
                  {DATA_SOURCES.map((source) => (
                    <option key={source} value={source}>
                      {source}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="section-query-path">Path</Label>
                <Input
                  id="section-query-path"
                  value={draft.query?.path ?? ""}
                  onChange={(event) => setDraft({ ...draft, query: { ...(draft.query ?? { source: "inventory" as DataSourceValue }), path: event.target.value } })}
                  placeholder="/inventory/search"
                />
              </div>
            </div>
          </div>
        )}

        {draft.kind === "table" && (
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">Columns</p>
            {(draft.columns ?? []).map((column, index) => (
              <div key={index} className="flex gap-2">
                <Input value={column.key} onChange={(event) => updateColumn(index, { key: event.target.value })} placeholder="key" className="flex-1" />
                <Input value={column.label} onChange={(event) => updateColumn(index, { label: event.target.value })} placeholder="label" className="flex-1" />
                <Button variant="ghost" onClick={() => removeColumn(index)}>
                  Remove
                </Button>
              </div>
            ))}
            <Button variant="outline" onClick={addColumn} className="w-fit">
              Add column
            </Button>
          </div>
        )}

        {draft.kind === "chart" && (
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="section-chart-kind">Chart kind</Label>
              <Select
                id="section-chart-kind"
                value={draft.chart?.kind ?? "bar"}
                onChange={(event) => setDraft({ ...draft, chart: { ...(draft.chart ?? { labelKey: "", valueKey: "" }), kind: event.target.value as ChartKindValue } })}
              >
                {CHART_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {kind}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="section-chart-label-key">Label key</Label>
              <Input
                id="section-chart-label-key"
                value={draft.chart?.labelKey ?? ""}
                onChange={(event) => setDraft({ ...draft, chart: { ...(draft.chart ?? { kind: "bar", valueKey: "" }), labelKey: event.target.value } })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="section-chart-value-key">Value key</Label>
              <Input
                id="section-chart-value-key"
                value={draft.chart?.valueKey ?? ""}
                onChange={(event) => setDraft({ ...draft, chart: { ...(draft.chart ?? { kind: "bar", labelKey: "" }), valueKey: event.target.value } })}
              />
            </div>
          </div>
        )}

        {draft.kind === "metric" && (
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="section-metric-aggregate">Aggregate</Label>
              <Select id="section-metric-aggregate" value={draft.metricAggregate ?? "count"} onChange={(event) => setDraft({ ...draft, metricAggregate: event.target.value as MetricAggregate })}>
                {METRIC_AGGREGATES.map((aggregate) => (
                  <option key={aggregate} value={aggregate}>
                    {aggregate}
                  </option>
                ))}
              </Select>
            </div>
            {draft.metricAggregate !== "count" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="section-metric-key">Metric key</Label>
                <Input id="section-metric-key" value={draft.metricKey ?? ""} onChange={(event) => setDraft({ ...draft, metricKey: event.target.value })} />
              </div>
            )}
          </div>
        )}

        {error && <p className="text-danger text-sm">{error}</p>}
      </div>
    </Dialog>
  );
}
