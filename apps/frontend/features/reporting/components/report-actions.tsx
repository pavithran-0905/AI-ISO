"use client";

import { Play, Star, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { AskAiButton } from "@/features/ai-assistant/components/ask-ai-button";
import { GenerateReportDialog } from "@/features/reporting/components/generate-report-dialog";
import { useDeleteReport, useFavoriteReports, useToggleFavorite } from "@/features/reporting/hooks/use-reports";
import type { GenerateResult, Report } from "@/features/reporting/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

/**
 * Generate/Favorite/Edit/Delete (§6/§13) — the real mutation set this
 * prompt covers. Delete is a real soft delete (`DELETE /reports/{id}`),
 * confirmed via dialog before it fires, gated behind the coarse role
 * capability model as a UX convenience (§25) since the backend performs
 * no permission check on any of these routes.
 */
export function ReportActions({ organizationId, report, onGenerated }: { organizationId: string; report: Report; onGenerated: (result: GenerateResult) => void }) {
  const router = useRouter();
  const { can } = usePermissions();
  const [generateOpen, setGenerateOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const favoritesQuery = useFavoriteReports(organizationId);
  const toggleFavorite = useToggleFavorite();
  const deleteReport = useDeleteReport();

  const favorited = (favoritesQuery.data ?? []).some((favorite) => favorite.id === report.id);

  async function handleDelete() {
    try {
      await deleteReport.mutateAsync(report.id);
      toast.success("Report deleted");
      router.push("/reporting/reports");
    } catch {
      toast.danger("Failed to delete report", "Please try again.");
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {can("execute") && (
        <Button onClick={() => setGenerateOpen(true)} className="gap-1.5">
          <Play className="size-4" aria-hidden="true" />
          Generate
        </Button>
      )}
      <Button
        variant="outline"
        onClick={() => toggleFavorite.mutate({ reportId: report.id, favorited })}
        loading={toggleFavorite.isPending}
        className="gap-1.5"
      >
        <Star className={favorited ? "size-4 fill-current" : "size-4"} aria-hidden="true" />
        {favorited ? "Favorited" : "Favorite"}
      </Button>
      {can("update") && (
        <Link href={`/reporting/reports/${report.id}/edit`} className={buttonVariants("outline")}>
          Edit
        </Link>
      )}
      {can("delete") && (
        <Button variant="danger" onClick={() => setDeleteOpen(true)} className="gap-1.5">
          <Trash2 className="size-4" aria-hidden="true" />
          Delete
        </Button>
      )}
      <AskAiButton draft={`Tell me about the report "${report.name}" (id: ${report.id}).`} />

      <GenerateReportDialog report={report} open={generateOpen} onClose={() => setGenerateOpen(false)} onGenerated={onGenerated} />

      <Dialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="Delete this report?"
        description="This removes it from every list. Already-generated exports and archives are unaffected."
        footer={
          <>
            <Button variant="outline" onClick={() => setDeleteOpen(false)} disabled={deleteReport.isPending}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} loading={deleteReport.isPending}>
              Delete
            </Button>
          </>
        }
      />
    </div>
  );
}
