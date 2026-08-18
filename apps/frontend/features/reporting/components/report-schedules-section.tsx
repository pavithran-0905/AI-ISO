"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Card, CardContent } from "@/components/data-display/card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Switch } from "@/components/forms/switch";
import { SectionState } from "@/features/dashboard/components/section-state";
import { ScheduleFormDialog } from "@/features/reporting/components/schedule-form-dialog";
import { useDeleteSchedule, useSchedules, useUpdateSchedule } from "@/features/reporting/hooks/use-schedules";
import type { ExportFormat, ReportSchedule } from "@/features/reporting/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

/**
 * Real schedules for this one report (§15/§16) — enable/disable is the
 * `enabled` field on `ScheduleUpdateRequest`, not a dedicated endpoint;
 * `starts_at` can't be edited once a schedule exists (only create-new
 * changes it), so there is no "edit" action here beyond enable/disable
 * and delete.
 */
export function ReportSchedulesSection({ organizationId, reportId, defaultFormat }: { organizationId: string; reportId: string; defaultFormat: ExportFormat }) {
  const { can } = usePermissions();
  const [dialogOpen, setDialogOpen] = useState(false);
  const query = useSchedules(organizationId, reportId);
  const deleteSchedule = useDeleteSchedule();

  return (
    <div className="flex flex-col gap-3">
      {can("execute") && (
        <Button variant="outline" onClick={() => setDialogOpen(true)} className="w-fit gap-1.5">
          <Plus className="size-4" aria-hidden="true" />
          New schedule
        </Button>
      )}

      <SectionState isLoading={query.isLoading} isError={query.isError} error={query.error} onRetry={() => query.refetch()}>
        {query.data &&
          (query.data.length === 0 ? (
            <EmptyState title="No schedules for this report" description="This report only runs when generated manually." />
          ) : (
            <ul className="flex flex-col gap-2">
              {query.data.map((schedule) => (
                <ScheduleRow key={schedule.id} schedule={schedule} canManage={can("execute")} onDelete={() => deleteSchedule.mutate(schedule.id)} />
              ))}
            </ul>
          ))}
      </SectionState>

      <ScheduleFormDialog organizationId={organizationId} reportId={reportId} defaultFormat={defaultFormat} open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </div>
  );
}

function ScheduleRow({ schedule, canManage, onDelete }: { schedule: ReportSchedule; canManage: boolean; onDelete: () => void }) {
  const updateSchedule = useUpdateSchedule(schedule.id);

  async function handleToggle(enabled: boolean) {
    try {
      await updateSchedule.mutateAsync({ enabled });
    } catch {
      toast.danger("Failed to update schedule");
    }
  }

  return (
    <li>
      <Card>
        <CardContent className="flex items-center justify-between gap-3 p-3">
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-medium">
              {schedule.frequency.replace("_", " ")} · {schedule.timezone}
            </p>
            <p className="text-muted-foreground text-xs">
              {schedule.nextRunAt ? (
                <>
                  Next run <time dateTime={schedule.nextRunAt}>{formatRelativeTime(schedule.nextRunAt)}</time>
                </>
              ) : (
                "No upcoming run"
              )}
              {schedule.consecutiveFailures > 0 && ` · ${schedule.consecutiveFailures} consecutive failures`}
            </p>
            {schedule.lastError && <p className="text-danger text-xs">{schedule.lastError}</p>}
          </div>
          <div className="flex items-center gap-2">
            {canManage && (
              <>
                <Switch checked={schedule.enabled} onChange={(event) => handleToggle(event.target.checked)} aria-label={schedule.enabled ? "Disable schedule" : "Enable schedule"} />
                <IconButton icon={Trash2} aria-label="Delete schedule" variant="ghost" onClick={onDelete} />
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </li>
  );
}
