"use client";

import { Upload } from "lucide-react";
import { useRef, useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Checkbox } from "@/components/forms/checkbox";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Dialog } from "@/components/overlays/dialog";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Button } from "@/components/ui/button";
import { useCreateImport, useImportJob, useRollbackImport } from "@/features/infrastructure/hooks/use-import";
import { IMPORT_EXPORT_JOB_STATUS_TONE } from "@/features/infrastructure/lib/status-maps";
import { IMPORT_FORMATS, type ImportFormatValue } from "@/features/infrastructure/types";
import { toast } from "@/state/toast-store";

/**
 * A real, async, job-based import (§26), with the two capabilities
 * docs/036's own "IMPORT" section calls for beyond the literal REST
 * list: Preview (`previewOnly`, never writes anything) and Rollback
 * (undoes a completed, non-preview import).
 */
export function ImportDialog({ organizationId, open, onClose }: { organizationId: string; open: boolean; onClose: () => void }) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [sourceFormat, setSourceFormat] = useState<ImportFormatValue>("json");
  const [previewOnly, setPreviewOnly] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const createImport = useCreateImport();
  const rollbackImport = useRollbackImport();
  const jobQuery = useImportJob(jobId);

  async function handleStart(event: React.FormEvent) {
    event.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;
    try {
      const job = await createImport.mutateAsync({ organizationId, file, sourceFormat, previewOnly });
      setJobId(job.jobId);
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not start import", message);
    }
  }

  async function handleRollback() {
    if (!jobId) return;
    try {
      await rollbackImport.mutateAsync(jobId);
      toast.success("Import rolled back");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not roll back import", message);
    }
  }

  function handleClose() {
    setJobId(null);
    onClose();
  }

  const job = jobQuery.data;

  return (
    <Dialog open={open} onClose={handleClose} title="Import assets" description="Runs as a background job. Preview mode validates the file without writing anything.">
      <div className="flex flex-col gap-4">
        {!jobId && (
          <form onSubmit={(event) => void handleStart(event)} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="import-file">File</Label>
              <input
                id="import-file"
                ref={fileInputRef}
                type="file"
                required
                className="text-sm file:mr-3 file:rounded-md file:border file:border-border file:bg-transparent file:px-3 file:py-1.5 file:text-sm"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="import-format">Format</Label>
              <Select id="import-format" value={sourceFormat} onChange={(event) => setSourceFormat(event.target.value as ImportFormatValue)}>
                {IMPORT_FORMATS.map((format) => (
                  <option key={format} value={format}>
                    {format.toUpperCase()}
                  </option>
                ))}
              </Select>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={previewOnly} onChange={(event) => setPreviewOnly(event.target.checked)} />
              Preview only (validate without writing)
            </label>
            <Button type="submit" loading={createImport.isPending} className="w-fit gap-1.5">
              <Upload className="size-4" aria-hidden="true" />
              Start import
            </Button>
          </form>
        )}

        {jobId && (
          <div className="flex flex-col gap-3">
            {job ? (
              <>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm">Job status</span>
                  <StatusBadge tone={IMPORT_EXPORT_JOB_STATUS_TONE[job.status]} label={job.status} />
                </div>
                <dl className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <dt className="text-muted-foreground text-xs">Total rows</dt>
                    <dd>{job.totalRows}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground text-xs">Processed</dt>
                    <dd>{job.processedRows}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground text-xs">Succeeded</dt>
                    <dd>{job.succeededRows}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground text-xs">Failed</dt>
                    <dd>{job.failedRows}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground text-xs">Duplicates</dt>
                    <dd>{job.duplicateRows}</dd>
                  </div>
                </dl>
                {job.errorReport.length > 0 && (
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium">Errors</p>
                    <pre className="bg-muted max-h-40 overflow-auto rounded p-2 text-xs">
                      {JSON.stringify(job.errorReport, null, 2)}
                    </pre>
                  </div>
                )}
                {job.status === "completed" && !job.previewOnly && (
                  <Button variant="danger" onClick={() => void handleRollback()} loading={rollbackImport.isPending} className="w-fit">
                    Roll back this import
                  </Button>
                )}
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
