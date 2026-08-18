"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/forms/checkbox";
import { Dialog } from "@/components/overlays/dialog";
import { Label } from "@/components/forms/label";
import { useGenerateReport } from "@/features/reporting/hooks/use-reports";
import { EXPORT_FORMATS, type ExportFormat, type GenerateResult, type Report } from "@/features/reporting/types";
import { toast } from "@/state/toast-store";

/**
 * `POST /reports/generate` (§13) is synchronous — this dialog stays
 * open with a loading state for the whole render+export pipeline and
 * shows the complete, real result (or a real failure) when the request
 * resolves. No polling, no fabricated "queued" status — the backend
 * has no job-status endpoint to poll (§13: "do not invent statuses").
 */
export function GenerateReportDialog({
  report,
  open,
  onClose,
  onGenerated,
}: {
  report: Report;
  open: boolean;
  onClose: () => void;
  onGenerated: (result: GenerateResult) => void;
}) {
  const [formats, setFormats] = useState<ExportFormat[]>([report.defaultFormat]);
  const [distribute, setDistribute] = useState(false);
  const [archive, setArchive] = useState(false);
  const generate = useGenerateReport();

  function toggleFormat(format: ExportFormat) {
    setFormats((current) => (current.includes(format) ? current.filter((f) => f !== format) : [...current, format]));
  }

  async function handleGenerate() {
    try {
      const result = await generate.mutateAsync({
        reportId: report.id,
        exportFormats: formats,
        parameterValues: report.parameterValues,
        filters: report.filters,
        distribute,
        archive,
      });
      toast.success("Report generated");
      onGenerated(result);
      onClose();
    } catch {
      toast.danger("Generation failed", "The report could not be generated. Check its template and parameters.");
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Generate report"
      description={`Uses ${report.name}'s saved parameters and filters.`}
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={generate.isPending}>
            Cancel
          </Button>
          <Button onClick={handleGenerate} loading={generate.isPending} disabled={formats.length === 0}>
            Generate
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label>Export formats</Label>
          <div className="flex flex-wrap gap-3">
            {EXPORT_FORMATS.map((format) => (
              <label key={format} className="flex items-center gap-1.5 text-sm">
                <Checkbox checked={formats.includes(format)} onChange={() => toggleFormat(format)} />
                {format.toUpperCase()}
              </label>
            ))}
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={distribute} onChange={(event) => setDistribute(event.target.checked)} />
          Deliver to this report&rsquo;s standing recipients
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={archive} onChange={(event) => setArchive(event.target.checked)} />
          Archive the result immediately
        </label>
      </div>
    </Dialog>
  );
}
