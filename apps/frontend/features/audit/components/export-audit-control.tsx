"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { Alert } from "@/components/feedback/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { useExportComplianceAudit } from "@/features/audit/hooks/use-audit";
import { AUDIT_REPORT_FORMATS, type AuditReportFormatValue } from "@/features/audit/types";

const FORMAT_LABELS: Record<AuditReportFormatValue, string> = { json: "JSON", csv: "CSV", markdown: "Markdown" };

/**
 * §30: real export, `compliance` source only (see `AuditReportRequest`'s
 * docstring for why `integrations`/`notifications` have none, and why
 * this doesn't route through Reporting). The exported file's rows are
 * narrower than the live table — noted inline rather than left as a
 * surprise.
 */
export function ExportAuditControl({ organizationId }: { organizationId: string }) {
  const [format, setFormat] = useState<AuditReportFormatValue>("csv");
  const exportMutation = useExportComplianceAudit();

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="audit-export-format">Export format</Label>
          <Select id="audit-export-format" value={format} onChange={(event) => setFormat(event.target.value as AuditReportFormatValue)} className="w-32">
            {AUDIT_REPORT_FORMATS.map((value) => (
              <option key={value} value={value}>
                {FORMAT_LABELS[value]}
              </option>
            ))}
          </Select>
        </div>
        <Button
          variant="outline"
          loading={exportMutation.isPending}
          onClick={() => exportMutation.mutate({ organizationId, reportFormat: format, periodDays: 90 })}
          className="gap-1.5"
        >
          <Download className="size-4" aria-hidden="true" />
          Export last 90 days
        </Button>
      </div>
      <p className="text-muted-foreground text-xs">
        Exported rows carry fewer fields than the live table — no event ID, resource ID, actor type, or change detail.
      </p>
      {exportMutation.isError && (
        <Alert tone="danger" title="Export failed">
          {exportMutation.error instanceof Error ? exportMutation.error.message : "Please try again."}
        </Alert>
      )}
    </div>
  );
}
