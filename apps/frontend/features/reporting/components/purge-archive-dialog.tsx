"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { usePurgeArchive } from "@/features/reporting/hooks/use-archive";
import { toast } from "@/state/toast-store";

/**
 * `DELETE /reports/archive/{id}` (§19/§20) — the backend rejects this
 * with a 409 and its own real message if the artifact is still inside
 * its retention window or already purged
 * (`ArchiveRetentionPolicy.ensure_purgeable`). That backend-confirmed
 * reason is shown verbatim, per §20's own instruction — never a
 * generic "action failed," and never silently bypassed.
 */
export function PurgeArchiveDialog({ archiveId, title, open, onClose }: { archiveId: string; title: string; open: boolean; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const purge = usePurgeArchive();

  async function handlePurge() {
    try {
      await purge.mutateAsync({ archiveId, reason: reason.trim() || undefined });
      toast.success("Archive purged");
      onClose();
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not purge this archive", message);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`Purge "${title}"?`}
      description="This permanently removes the archived content. Metadata is kept for audit purposes."
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={purge.isPending}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handlePurge} loading={purge.isPending}>
            Purge
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="purge-reason">Reason (optional)</Label>
        <Input id="purge-reason" value={reason} onChange={(event) => setReason(event.target.value)} />
      </div>
    </Dialog>
  );
}
