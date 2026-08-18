"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/overlays/dialog";
import { Label } from "@/components/forms/label";
import { Textarea } from "@/components/forms/textarea";
import { AskAiButton } from "@/features/ai-assistant/components/ask-ai-button";
import { useAcknowledgeAlert } from "@/features/alerting/hooks/use-acknowledge-alert";
import { useCloseAlert } from "@/features/alerting/hooks/use-close-alert";
import { useEscalateAlert } from "@/features/alerting/hooks/use-escalate-alert";
import { useResolveAlert } from "@/features/alerting/hooks/use-resolve-alert";
import { RESOLVED_ALERT_STATUSES, type Alert } from "@/features/alerting/types";
import { usePermissions } from "@/permissions/hooks";
import { toast } from "@/state/toast-store";

type ActionKind = "acknowledge" | "resolve" | "escalate" | "close";

const ACTION_COPY: Record<ActionKind, { title: string; confirmLabel: string; fieldLabel?: string; placeholder?: string; successTitle: string }> = {
  acknowledge: {
    title: "Acknowledge alert",
    confirmLabel: "Acknowledge",
    fieldLabel: "Comment (optional)",
    placeholder: "Add context for whoever looks at this next…",
    successTitle: "Alert acknowledged",
  },
  resolve: {
    title: "Resolve alert",
    confirmLabel: "Resolve",
    fieldLabel: "Resolution notes (optional)",
    placeholder: "What fixed it?",
    successTitle: "Alert resolved",
  },
  escalate: {
    title: "Escalate alert",
    confirmLabel: "Escalate",
    fieldLabel: "Reason (optional)",
    placeholder: "Why does this need escalation?",
    successTitle: "Alert escalated",
  },
  close: {
    title: "Close alert",
    confirmLabel: "Close",
    successTitle: "Alert closed",
  },
};

/**
 * Acknowledge/Resolve/Escalate/Close (§11-§14) — the exact mutation set
 * confirmed to exist on `services/alerting-service` (no Reopen, no
 * Suppress/Unsuppress: neither has a backend route despite the internal
 * state machine permitting some of these transitions). Each waits for
 * the backend's confirmed response (no optimistic update — see every
 * `use-*-alert.ts` hook's own docstring), disables its button while
 * pending (built into `Button`'s `loading` prop, preventing duplicate
 * submission), and reports success/failure via toast.
 *
 * The lifecycle mutations (not "Ask AI") are hidden once an alert is
 * already resolved/closed/expired (`RESOLVED_ALERT_STATUSES`) — there's
 * nothing left to acknowledge, resolve, or escalate, and no backend
 * "reopen" route exists to undo it. This is a lifecycle-state UX
 * heuristic, not a simulation of backend authorization.
 *
 * Button visibility is gated by the coarse role-based capability model
 * (`@/permissions`) as a UX convenience only — §25: the backend
 * performs no permission check on any alerting route today, so hiding
 * a button here only saves a wasted click, never enforces anything.
 */
export function AlertActions({ alert }: { alert: Alert }) {
  const { can } = usePermissions();
  const [openAction, setOpenAction] = useState<ActionKind | null>(null);
  const [note, setNote] = useState("");

  const acknowledge = useAcknowledgeAlert(alert.id);
  const resolve = useResolveAlert(alert.id);
  const escalate = useEscalateAlert(alert.id);
  const close = useCloseAlert(alert.id);

  const isResolved = RESOLVED_ALERT_STATUSES.has(alert.status);

  function openDialog(kind: ActionKind) {
    setNote("");
    setOpenAction(kind);
  }

  function closeDialog() {
    setOpenAction(null);
  }

  async function handleConfirm() {
    if (!openAction) return;
    const copy = ACTION_COPY[openAction];
    try {
      if (openAction === "acknowledge") await acknowledge.mutateAsync(note || undefined);
      else if (openAction === "resolve") await resolve.mutateAsync(note || undefined);
      else if (openAction === "escalate") await escalate.mutateAsync(note ? { reason: note } : undefined);
      else await close.mutateAsync();
      toast.success(copy.successTitle);
      closeDialog();
    } catch {
      toast.danger(`Failed to ${openAction} alert`, "Please try again.");
    }
  }

  const isPending = acknowledge.isPending || resolve.isPending || escalate.isPending || close.isPending;
  const copy = openAction ? ACTION_COPY[openAction] : null;

  return (
    <div className="flex flex-wrap gap-2">
      {!isResolved && can("update") && (
        <Button variant="outline" onClick={() => openDialog("acknowledge")} disabled={isPending}>
          Acknowledge
        </Button>
      )}
      {!isResolved && can("update") && (
        <Button variant="outline" onClick={() => openDialog("resolve")} disabled={isPending}>
          Resolve
        </Button>
      )}
      {!isResolved && can("execute") && (
        <Button variant="outline" onClick={() => openDialog("escalate")} disabled={isPending}>
          Escalate
        </Button>
      )}
      {!isResolved && can("update") && (
        <Button variant="danger" onClick={() => openDialog("close")} disabled={isPending}>
          Close
        </Button>
      )}
      <AskAiButton draft={`Tell me about alert "${alert.title}" (id: ${alert.id}).`} />

      {copy && (
        <Dialog
          open={openAction !== null}
          onClose={closeDialog}
          title={copy.title}
          footer={
            <>
              <Button variant="outline" onClick={closeDialog} disabled={isPending}>
                Cancel
              </Button>
              <Button onClick={handleConfirm} loading={isPending}>
                {copy.confirmLabel}
              </Button>
            </>
          }
        >
          {copy.fieldLabel && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="alert-action-note">{copy.fieldLabel}</Label>
              <Textarea
                id="alert-action-note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder={copy.placeholder}
              />
            </div>
          )}
        </Dialog>
      )}
    </div>
  );
}
