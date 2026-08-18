"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { SectionState } from "@/features/dashboard/components/section-state";
import { RecipientFormDialog } from "@/features/reporting/components/recipient-form-dialog";
import { useDeleteRecipient, useRecipients } from "@/features/reporting/hooks/use-distribution";
import type { ExportFormat } from "@/features/reporting/types";
import { usePermissions } from "@/permissions/hooks";

/** Standing recipients for this report (§17) — used when generating
 * with "distribute" checked, or ad hoc from a specific export. */
export function ReportRecipientsSection({ organizationId, reportId, defaultFormat }: { organizationId: string; reportId: string; defaultFormat: ExportFormat }) {
  const { can } = usePermissions();
  const [dialogOpen, setDialogOpen] = useState(false);
  const query = useRecipients(reportId);
  const deleteRecipient = useDeleteRecipient(reportId);

  return (
    <div className="flex flex-col gap-3">
      {can("export") && (
        <Button variant="outline" onClick={() => setDialogOpen(true)} className="w-fit gap-1.5">
          <Plus className="size-4" aria-hidden="true" />
          Add recipient
        </Button>
      )}

      <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
        {query.data &&
          (query.data.length === 0 ? (
            <EmptyState title="No standing recipients" description="Generations won't be delivered anywhere automatically." />
          ) : (
            <ul className="flex flex-col gap-2">
              {query.data.map((recipient) => (
                <li key={recipient.id}>
                  <Card>
                    <CardContent className="flex items-center justify-between gap-3 p-3">
                      <div className="flex flex-col gap-0.5">
                        <p className="text-sm font-medium">{recipient.channel.replace("_", " ")}</p>
                        <p className="text-muted-foreground text-xs">
                          {recipient.target} · {recipient.exportFormat.toUpperCase()}
                        </p>
                      </div>
                      {can("export") && (
                        <IconButton icon={Trash2} aria-label="Remove recipient" variant="ghost" onClick={() => deleteRecipient.mutate(recipient.id)} />
                      )}
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
          ))}
      </SectionState>

      <RecipientFormDialog organizationId={organizationId} reportId={reportId} defaultFormat={defaultFormat} open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </div>
  );
}
