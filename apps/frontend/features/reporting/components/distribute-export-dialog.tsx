"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { useDistributeExport } from "@/features/reporting/hooks/use-distribution";
import { DISTRIBUTION_CHANNELS, type DistributionChannelValue } from "@/features/reporting/types";
import { toast } from "@/state/toast-store";

/** `POST /reports/exports/{id}/distribute` (§17) — a one-off delivery,
 * distinct from a standing recipient subscription. No credential/secret
 * field is collected (§17). */
export function DistributeExportDialog({ exportId, open, onClose }: { exportId: string; open: boolean; onClose: () => void }) {
  const [channel, setChannel] = useState<DistributionChannelValue>("email");
  const [target, setTarget] = useState("");
  const distribute = useDistributeExport();

  async function handleSend() {
    try {
      await distribute.mutateAsync({ exportId, input: { channel, target } });
      toast.success("Delivery attempted");
      onClose();
    } catch {
      toast.danger("Delivery failed", "Please check the target and try again.");
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Distribute this export"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={distribute.isPending}>
            Cancel
          </Button>
          <Button onClick={handleSend} loading={distribute.isPending}>
            Send
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="distribute-channel">Channel</Label>
          <Select id="distribute-channel" value={channel} onChange={(event) => setChannel(event.target.value as DistributionChannelValue)}>
            {DISTRIBUTION_CHANNELS.map((value) => (
              <option key={value} value={value}>
                {value.replace("_", " ")}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="distribute-target">Target</Label>
          <Input id="distribute-target" value={target} onChange={(event) => setTarget(event.target.value)} />
        </div>
      </div>
    </Dialog>
  );
}
