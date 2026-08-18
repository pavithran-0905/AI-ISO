"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { GenerationResult } from "@/features/reporting/components/generation-result";
import { ReportActions } from "@/features/reporting/components/report-actions";
import { ReportHistorySection } from "@/features/reporting/components/report-history-section";
import { ReportRecipientsSection } from "@/features/reporting/components/report-recipients-section";
import { ReportSchedulesSection } from "@/features/reporting/components/report-schedules-section";
import type { GenerateResult, Report } from "@/features/reporting/types";

/**
 * Report Detail (§6) — Identity → Actions → Latest generation →
 * Schedule → Distribution → History. No "Available exports" section
 * beyond the latest generation's own: there is no `GET /reports/{id}/executions`
 * to list past runs, so historical exports aren't independently
 * browsable — see `docs/frontend/backend-v1-integration-limitations.md`.
 * No "Archive information" section here either: archive entries aren't
 * filterable by report id on `GET /reports/archive` (only `search`/`status`),
 * so this page can't reliably show "this report's archive" — see the
 * same limitations doc. AI narrative content isn't shown separately
 * either — it's one section kind inside a generated export, visible by
 * downloading/opening the artifact itself (§21/§22).
 */
export function ReportDetailView({ organizationId, report }: { organizationId: string; report: Report }) {
  const [lastResult, setLastResult] = useState<GenerateResult | null>(null);

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <Field label="Category" value={report.category} />
            <Field label="Type" value={report.reportType} />
            <Field label="Default format" value={report.defaultFormat.toUpperCase()} />
            <Field label="Template id" value={report.templateId} mono />
            <Field label="Owner id" value={report.ownerId} mono />
            <div className="flex flex-col gap-0.5">
              <dt className="text-muted-foreground text-xs">Status</dt>
              <dd>
                <StatusBadge tone={report.enabled ? "success" : "neutral"} label={report.enabled ? "Enabled" : "Disabled"} />
              </dd>
            </div>
          </dl>
          {report.description && <p className="text-muted-foreground mt-4 text-sm">{report.description}</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <ReportActions organizationId={organizationId} report={report} onGenerated={setLastResult} />
        </CardContent>
      </Card>

      {lastResult && <GenerationResult result={lastResult} />}

      <Card>
        <CardHeader>
          <CardTitle>Schedule</CardTitle>
        </CardHeader>
        <CardContent>
          <ReportSchedulesSection organizationId={organizationId} reportId={report.id} defaultFormat={report.defaultFormat} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <ReportRecipientsSection organizationId={organizationId} reportId={report.id} defaultFormat={report.defaultFormat} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent>
          <ReportHistorySection organizationId={organizationId} reportId={report.id} />
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string | null; mono?: boolean }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className={mono ? "font-mono text-xs" : "text-sm"}>{value}</dd>
    </div>
  );
}
