"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { useCreateSchedule } from "@/features/reporting/hooks/use-schedules";
import { EXPORT_FORMATS, SCHEDULE_FREQUENCIES, type ExportFormat, type ScheduleFrequencyValue } from "@/features/reporting/types";
import { toast } from "@/state/toast-store";

/** IANA zone names — there is no timezone-list endpoint on
 * `reporting-service` (it only validates a caller-supplied string), so
 * this uses the browser's own real timezone database
 * (`Intl.supportedValuesOf`) rather than a hand-maintained or invented
 * list. Falls back to a short, common set on a browser too old to
 * support the API. */
function supportedTimezones(): string[] {
  if (typeof Intl.supportedValuesOf === "function") {
    return Intl.supportedValuesOf("timeZone");
  }
  return ["UTC", "America/New_York", "America/Los_Angeles", "Europe/London", "Europe/Berlin", "Asia/Kolkata", "Asia/Tokyo", "Australia/Sydney"];
}

/**
 * Real schedule creation (§15/§16), against the exact fields
 * `ScheduleCreateRequest` accepts — `starts_at`/timezone/recurrence
 * validated by the backend itself (`app/scheduler/recurrence.py`), not
 * re-implemented or guessed at client-side.
 */
export function ScheduleFormDialog({
  organizationId,
  reportId,
  defaultFormat,
  open,
  onClose,
}: {
  organizationId: string;
  reportId: string;
  defaultFormat: ExportFormat;
  open: boolean;
  onClose: () => void;
}) {
  const [frequency, setFrequency] = useState<ScheduleFrequencyValue>("daily");
  const [cronExpression, setCronExpression] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [exportFormat, setExportFormat] = useState<ExportFormat>(defaultFormat);
  const [error, setError] = useState<string | null>(null);
  const createSchedule = useCreateSchedule();

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!startsAt) {
      setError("A start date/time is required.");
      return;
    }
    if (frequency === "cron" && !cronExpression.trim()) {
      setError("A cron expression is required for a custom schedule.");
      return;
    }
    setError(null);
    try {
      await createSchedule.mutateAsync({
        organizationId,
        reportId,
        frequency,
        startsAt: new Date(startsAt).toISOString(),
        endsAt: endsAt ? new Date(endsAt).toISOString() : undefined,
        cronExpression: frequency === "cron" ? cronExpression.trim() : undefined,
        timezone,
        exportFormat,
      });
      toast.success("Schedule created");
      onClose();
    } catch {
      toast.danger("Failed to create schedule", "Check the recurrence and timezone, then try again.");
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Schedule this report"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={createSchedule.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="schedule-form" loading={createSchedule.isPending}>
            Create schedule
          </Button>
        </>
      }
    >
      <form id="schedule-form" onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="schedule-frequency">Frequency</Label>
          <Select id="schedule-frequency" value={frequency} onChange={(event) => setFrequency(event.target.value as ScheduleFrequencyValue)}>
            {SCHEDULE_FREQUENCIES.map((value) => (
              <option key={value} value={value}>
                {value.replace("_", " ")}
              </option>
            ))}
          </Select>
        </div>

        {frequency === "cron" && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="schedule-cron">Cron expression</Label>
            <Input id="schedule-cron" value={cronExpression} onChange={(event) => setCronExpression(event.target.value)} placeholder="0 9 * * MON" />
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="schedule-timezone">Timezone</Label>
          <Select id="schedule-timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)}>
            {supportedTimezones().map((zone) => (
              <option key={zone} value={zone}>
                {zone}
              </option>
            ))}
          </Select>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="schedule-starts">Starts</Label>
            <Input id="schedule-starts" type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} required />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="schedule-ends">Ends (optional)</Label>
            <Input id="schedule-ends" type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="schedule-format">Export format</Label>
          <Select id="schedule-format" value={exportFormat} onChange={(event) => setExportFormat(event.target.value as ExportFormat)}>
            {EXPORT_FORMATS.map((format) => (
              <option key={format} value={format}>
                {format.toUpperCase()}
              </option>
            ))}
          </Select>
        </div>

        {error && <p className="text-danger text-sm">{error}</p>}
      </form>
    </Dialog>
  );
}
