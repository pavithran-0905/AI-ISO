"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Dialog } from "@/components/overlays/dialog";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/feedback/status-badge";
import { useCreateExport, useExportJob } from "@/features/infrastructure/hooks/use-export";
import { IMPORT_EXPORT_JOB_STATUS_TONE } from "@/features/infrastructure/lib/status-maps";
import { ASSET_TYPES, EXPORT_FORMATS, type AssetTypeValue, type ExportFormatValue } from "@/features/infrastructure/types";
import { toast } from "@/state/toast-store";

/**
 * A real, async, job-based export (§25) — never a fake CSV that only
 * dumps the currently loaded page. Filters here mirror
 * `ExportRequest`'s own real, confirmed fields (`asset_type`/`status`/
 * `tags`) — never invented ones.
 */
export function ExportDialog({ organizationId, open, onClose }: { organizationId: string; open: boolean; onClose: () => void }) {
  const [targetFormat, setTargetFormat] = useState<ExportFormatValue>("json");
  const [assetType, setAssetType] = useState<AssetTypeValue | "">("");
  const [jobId, setJobId] = useState<string | null>(null);
  const createExport = useCreateExport();
  const jobQuery = useExportJob(jobId);

  async function handleStart() {
    try {
      const job = await createExport.mutateAsync({
        organizationId,
        targetFormat,
        assetType: assetType || undefined,
      });
      setJobId(job.jobId);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not start export", message);
    }
  }

  function handleClose() {
    setJobId(null);
    onClose();
  }

  const job = jobQuery.data;

  return (
    <Dialog open={open} onClose={handleClose} title="Export assets" description="Runs as a background job — this can take a moment for a large inventory.">
      <div className="flex flex-col gap-4">
        {!jobId && (
          <>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="export-format">Format</Label>
              <Select id="export-format" value={targetFormat} onChange={(event) => setTargetFormat(event.target.value as ExportFormatValue)}>
                {EXPORT_FORMATS.map((format) => (
                  <option key={format} value={format}>
                    {format.toUpperCase()}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="export-asset-type">Asset type (optional)</Label>
              <Select id="export-asset-type" value={assetType} onChange={(event) => setAssetType(event.target.value as AssetTypeValue | "")}>
                <option value="">All types</option>
                {ASSET_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </Select>
            </div>
            <Button onClick={() => void handleStart()} loading={createExport.isPending} className="w-fit gap-1.5">
              <Download className="size-4" aria-hidden="true" />
              Start export
            </Button>
          </>
        )}

        {jobId && (
          <div className="flex flex-col gap-3">
            {job ? (
              <>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm">Job status</span>
                  <StatusBadge tone={IMPORT_EXPORT_JOB_STATUS_TONE[job.status]} label={job.status} />
                </div>
                <p className="text-muted-foreground text-xs">{job.totalRows} row(s)</p>
                {job.downloadUrl && (
                  <a
                    href={job.downloadUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary text-sm font-medium hover:underline"
                  >
                    Download export
                  </a>
                )}
                {job.status === "failed" && <p className="text-danger text-sm">The export job failed.</p>}
              </>
            ) : (
              <p className="text-muted-foreground text-sm">Starting…</p>
            )}
          </div>
        )}
      </div>
    </Dialog>
  );
}
