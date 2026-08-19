"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { useDeleteAsset } from "@/features/infrastructure/hooks/use-assets";
import type { Asset } from "@/features/infrastructure/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

/**
 * Edit / Delete (§21) — the exact mutation set the backend really
 * supports beyond create (`PATCH`/`DELETE /inventory/assets/{id}`).
 * There is no dedicated enable/disable route — status is just another
 * `PATCH`-able field, exposed on the edit form instead of a separate
 * action. Delete is a real soft delete (§22: requires confirmation,
 * waits for the backend's confirmed response before navigating away).
 */
export function AssetActions({ asset }: { asset: Asset }) {
  const router = useRouter();
  const { can } = usePermissions();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const deleteAsset = useDeleteAsset();

  async function handleDelete() {
    try {
      await deleteAsset.mutateAsync(asset.id);
      toast.success("Asset deleted");
      router.push("/infrastructure/assets");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not delete asset", message);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {can("update") && (
        <Link href={`/infrastructure/assets/${asset.id}/edit`} className={buttonVariants("outline")}>
          Edit
        </Link>
      )}
      {can("delete") && (
        <Button variant="danger" onClick={() => setConfirmOpen(true)} className="gap-1.5">
          <Trash2 className="size-4" aria-hidden="true" />
          Delete
        </Button>
      )}

      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title={`Delete ${asset.displayName ?? asset.name}?`}
        description="This is a soft delete — the asset stops appearing anywhere in this UI. There is no restore endpoint."
        footer={
          <>
            <Button variant="outline" onClick={() => setConfirmOpen(false)} disabled={deleteAsset.isPending}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => void handleDelete()} loading={deleteAsset.isPending}>
              Delete
            </Button>
          </>
        }
      />
    </div>
  );
}
