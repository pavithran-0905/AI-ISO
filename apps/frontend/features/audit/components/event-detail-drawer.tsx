"use client";

import { Drawer } from "@/components/overlays/drawer";
import { StatusBadge } from "@/components/feedback/status-badge";
import { formatActionLabel } from "@/features/audit/lib/format";
import { maskSensitiveEntries } from "@/lib/mask-sensitive";
import { AUDIT_SOURCE_LABELS, type AuditEvent } from "@/features/audit/types";

function Field({ label, value, mono = false }: { label: string; value: string | null; mono?: boolean }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className={mono ? "font-mono text-xs break-all" : "text-sm"}>{value}</p>
    </div>
  );
}

function MetadataBlock({ label, value }: { label: string; value: Record<string, unknown> | null }) {
  if (!value || Object.keys(value).length === 0) return null;
  const masked = maskSensitiveEntries(value);
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-muted-foreground text-xs">{label}</p>
      <pre className="bg-muted overflow-x-auto rounded-md p-2 font-mono text-xs">{JSON.stringify(masked, null, 2)}</pre>
    </div>
  );
}

/**
 * §8's Event Detail, built as a drawer over the already-loaded list
 * row — never a `/audit/events/[id]` route or a second fetch, since no
 * service exposes a single-event-by-id GET (confirmed across all
 * three). §24: `changes`/`context` are masked by key name before
 * rendering, never logged to the console.
 */
export function EventDetailDrawer({ event, onClose }: { event: AuditEvent | null; onClose: () => void }) {
  return (
    <Drawer open={event !== null} onClose={onClose} title={event ? formatActionLabel(event.action) : "Event"}>
      {event && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <StatusBadge tone="info" label={AUDIT_SOURCE_LABELS[event.source]} />
            <StatusBadge tone={event.succeeded ? "success" : "danger"} label={event.succeeded ? "Success" : "Failure"} />
          </div>
          <Field label="Event ID" value={event.id} mono />
          <Field label="Actor" value={event.actorId} mono />
          <Field label="Actor type" value={event.actorType} />
          <Field label="Action" value={formatActionLabel(event.action)} />
          <Field label="Resource type" value={event.entityType} />
          <Field label="Resource" value={event.entityReference} />
          <Field label="Resource ID" value={event.entityId} mono />
          <Field label="Timestamp" value={new Date(event.occurredAt).toLocaleString()} />
          <Field label="Summary" value={event.summary} />
          <MetadataBlock label="Changes" value={event.changes} />
          <MetadataBlock label="Context" value={event.context} />
        </div>
      )}
    </Drawer>
  );
}
