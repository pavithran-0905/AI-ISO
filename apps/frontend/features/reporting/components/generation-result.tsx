"use client";

import { Archive as ArchiveIcon, Download, Send, Share2 } from "lucide-react";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/data-display/card";
import { Alert } from "@/components/feedback/alert";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { StatusBadge } from "@/components/feedback/status-badge";
import { ArchiveExportDialog } from "@/features/reporting/components/archive-export-dialog";
import { DistributeExportDialog } from "@/features/reporting/components/distribute-export-dialog";
import { ShareExportDialog } from "@/features/reporting/components/share-export-dialog";
import { useDownloadExport } from "@/features/reporting/hooks/use-reports";
import { formatBytes, formatDurationMs } from "@/features/reporting/lib/format-duration";
import { EXECUTION_STATUS_TONE } from "@/features/reporting/lib/status-tones";
import type { ExportArtifact, GenerateResult } from "@/features/reporting/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { usePermissions } from "@/permissions/hooks";

/**
 * The complete, real result of one `POST /reports/generate` call
 * (§10/§14) — this is the only place a generation's artifacts are ever
 * visible as a set; there is no `GET /reports/{id}/executions` to
 * re-fetch this later (see
 * `docs/frontend/backend-v1-integration-limitations.md`). `degradedSections`
 * is shown as a real, visible warning rather than a silently-incomplete
 * report (§13's own reasoning for why the backend surfaces it).
 */
export function GenerationResult({ result }: { result: GenerateResult }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Latest generation</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex flex-col gap-1">
            <p className="text-muted-foreground text-xs">Status</p>
            <StatusBadge tone={EXECUTION_STATUS_TONE[result.execution.status]} label={result.execution.status} />
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-muted-foreground text-xs">Rows</p>
            <p className="text-sm font-medium tabular-nums">{result.execution.rowCount}</p>
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-muted-foreground text-xs">Sections</p>
            <p className="text-sm font-medium tabular-nums">{result.execution.sectionCount}</p>
          </div>
          <div className="flex flex-col gap-1">
            <p className="text-muted-foreground text-xs">Duration</p>
            <p className="text-sm font-medium">{formatDurationMs(result.execution.durationMs) ?? "—"}</p>
          </div>
          {result.execution.finishedAt && (
            <div className="flex flex-col gap-1">
              <p className="text-muted-foreground text-xs">Finished</p>
              <p className="text-sm font-medium">
                <time dateTime={result.execution.finishedAt}>{formatRelativeTime(result.execution.finishedAt)}</time>
              </p>
            </div>
          )}
        </div>

        {result.execution.errorMessage && (
          <Alert tone="danger" title="Generation failed">
            {result.execution.errorMessage}
          </Alert>
        )}

        {result.degradedSections.length > 0 && (
          <Alert tone="warning" title="Some sections couldn't be resolved">
            Degraded: {result.degradedSections.join(", ")}. The rest of the report generated normally.
          </Alert>
        )}

        {result.exports.length > 0 && (
          <ul className="flex flex-col gap-2">
            {result.exports.map((artifact) => (
              <li key={artifact.id}>
                <ExportArtifactRow artifact={artifact} />
              </li>
            ))}
          </ul>
        )}

        {result.archiveId && <p className="text-muted-foreground text-xs">Archived — visible in the Archive tab.</p>}
      </CardContent>
    </Card>
  );
}

/** Download/Archive/Share/Distribute for one export artifact (§11/§17/
 * §18/§19) — the real per-export action set this prompt covers, beyond
 * the "distribute"/"archive immediately" checkboxes on the generate
 * dialog itself. */
function ExportArtifactRow({ artifact }: { artifact: ExportArtifact }) {
  const { can } = usePermissions();
  const download = useDownloadExport();
  const [dialog, setDialog] = useState<"archive" | "share" | "distribute" | null>(null);

  return (
    <div className="border-border flex flex-wrap items-center justify-between gap-3 rounded-md border p-3">
      <div className="flex flex-col gap-0.5">
        <p className="text-sm font-medium uppercase">{artifact.exportFormat}</p>
        <p className="text-muted-foreground text-xs">
          {artifact.filename} · {formatBytes(artifact.sizeBytes)}
        </p>
      </div>
      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          onClick={() => download.mutate({ exportId: artifact.id, filename: artifact.filename })}
          loading={download.isPending}
          className="gap-1.5"
        >
          <Download className="size-4" aria-hidden="true" />
          Download
        </Button>
        {can("export") && (
          <>
            <IconButton icon={ArchiveIcon} aria-label="Archive this export" variant="outline" onClick={() => setDialog("archive")} />
            <IconButton icon={Share2} aria-label="Create a share link" variant="outline" onClick={() => setDialog("share")} />
            <IconButton icon={Send} aria-label="Distribute this export" variant="outline" onClick={() => setDialog("distribute")} />
          </>
        )}
      </div>

      <ArchiveExportDialog exportId={artifact.id} defaultTitle={artifact.filename} open={dialog === "archive"} onClose={() => setDialog(null)} />
      <ShareExportDialog exportId={artifact.id} open={dialog === "share"} onClose={() => setDialog(null)} />
      <DistributeExportDialog exportId={artifact.id} open={dialog === "distribute"} onClose={() => setDialog(null)} />
    </div>
  );
}
