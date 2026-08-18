"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { useCreateRecipient } from "@/features/reporting/hooks/use-distribution";
import { DISTRIBUTION_CHANNELS, EXPORT_FORMATS, type DistributionChannelValue, type ExportFormat } from "@/features/reporting/types";
import { toast } from "@/state/toast-store";

const TARGET_PLACEHOLDER: Partial<Record<DistributionChannelValue, string>> = {
  email: "ops-team@example.com",
  webhook: "https://example.com/hooks/reports",
};

/** A standing subscription (§17) — real `DistributionChannel` values
 * only (`download/email/webhook/shared_link/api/object_storage`), not
 * a generic "email/Slack/Teams" list; no credential/secret field is
 * collected here (§17: "do not expose credentials/secrets in the UI"). */
export function RecipientFormDialog({
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
  const [channel, setChannel] = useState<DistributionChannelValue>("email");
  const [target, setTarget] = useState("");
  const [exportFormat, setExportFormat] = useState<ExportFormat>(defaultFormat);
  const [error, setError] = useState<string | null>(null);
  const createRecipient = useCreateRecipient(reportId);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!target.trim()) {
      setError("A target is required for this channel.");
      return;
    }
    setError(null);
    try {
      await createRecipient.mutateAsync({ organizationId, channel, target: target.trim(), exportFormat });
      toast.success("Recipient added");
      setTarget("");
      onClose();
    } catch {
      toast.danger("Failed to add recipient", "Check the target address/URL and try again.");
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Add recipient"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={createRecipient.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="recipient-form" loading={createRecipient.isPending}>
            Add recipient
          </Button>
        </>
      }
    >
      <form id="recipient-form" onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="recipient-channel">Channel</Label>
          <Select id="recipient-channel" value={channel} onChange={(event) => setChannel(event.target.value as DistributionChannelValue)}>
            {DISTRIBUTION_CHANNELS.map((value) => (
              <option key={value} value={value}>
                {value.replace("_", " ")}
              </option>
            ))}
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="recipient-target">Target</Label>
          <Input
            id="recipient-target"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            placeholder={TARGET_PLACEHOLDER[channel] ?? "Destination for this channel"}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="recipient-format">Export format</Label>
          <Select id="recipient-format" value={exportFormat} onChange={(event) => setExportFormat(event.target.value as ExportFormat)}>
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
