"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { useShareExport } from "@/features/reporting/hooks/use-distribution";
import { toast } from "@/state/toast-store";

/**
 * `POST /reports/exports/{id}/share` (§18) — the token is returned
 * exactly once, here; it's never fetchable again afterward (confirmed:
 * `DistributionResponse` deliberately omits it). There is no revoke
 * endpoint either — a link is only good until its own `expiresAt`
 * (see `docs/frontend/backend-v1-integration-limitations.md`).
 */
export function ShareExportDialog({ exportId, open, onClose }: { exportId: string; open: boolean; onClose: () => void }) {
  const share = useShareExport();
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (open && !share.data && !share.isPending) {
      share.mutate(exportId);
    }
    // Only trigger once when the dialog opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  async function handleCopy() {
    if (!share.data) return;
    await navigator.clipboard.writeText(share.data.shareToken);
    setCopied(true);
    toast.success("Link copied");
  }

  return (
    <Dialog
      open={open}
      onClose={() => {
        share.reset();
        setCopied(false);
        onClose();
      }}
      title="Share link"
      description="This token is shown once — copy it now. It can't be retrieved again later."
      footer={
        <Button variant="outline" onClick={onClose}>
          Close
        </Button>
      }
    >
      {share.isPending && <p className="text-muted-foreground text-sm">Creating link…</p>}
      {share.isError && <p className="text-danger text-sm">Failed to create a share link. Please try again.</p>}
      {share.data && (
        <div className="flex flex-col gap-3">
          <div className="border-border bg-muted break-all rounded-md border p-3 font-mono text-xs">{share.data.shareToken}</div>
          <Button variant="outline" onClick={handleCopy} className="w-fit gap-1.5">
            {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
            {copied ? "Copied" : "Copy token"}
          </Button>
          {share.data.expiresAt && (
            <p className="text-muted-foreground text-xs">
              Expires <time dateTime={share.data.expiresAt}>{new Date(share.data.expiresAt).toLocaleString()}</time>
            </p>
          )}
        </div>
      )}
    </Dialog>
  );
}
