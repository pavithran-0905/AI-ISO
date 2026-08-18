"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { useCreateArchive } from "@/features/reporting/hooks/use-archive";
import { toast } from "@/state/toast-store";

/** `POST /reports/archive` (§19), for archiving an already-generated
 * export after the fact — separate from the "archive immediately"
 * checkbox on the generate dialog, which does the same thing inline. */
export function ArchiveExportDialog({ exportId, defaultTitle, open, onClose }: { exportId: string; defaultTitle: string; open: boolean; onClose: () => void }) {
  const [title, setTitle] = useState(defaultTitle);
  const [retentionDays, setRetentionDays] = useState("");
  const createArchive = useCreateArchive();

  async function handleSave() {
    try {
      await createArchive.mutateAsync({
        exportId,
        title: title.trim() || defaultTitle,
        retentionDays: retentionDays ? Number(retentionDays) : undefined,
      });
      toast.success("Archived");
      onClose();
    } catch {
      toast.danger("Failed to archive", "Please try again.");
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Archive this export"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={createArchive.isPending}>
            Cancel
          </Button>
          <Button onClick={handleSave} loading={createArchive.isPending}>
            Archive
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="archive-title">Title</Label>
          <Input id="archive-title" value={title} onChange={(event) => setTitle(event.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="archive-retention">Retention days (optional)</Label>
          <Input id="archive-retention" type="number" min={1} max={36500} value={retentionDays} onChange={(event) => setRetentionDays(event.target.value)} placeholder="Uses the org default" />
        </div>
      </div>
    </Dialog>
  );
}
