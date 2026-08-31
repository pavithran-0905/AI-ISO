"use client";

import { X } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { formatActionLabel } from "@/features/audit/lib/format";
import { NOTIFICATIONS_AUDIT_ACTIONS, type AuditSourceValue } from "@/features/audit/types";

export interface AuditFilterValues {
  entityType: string;
  entityId: string;
  actorId: string;
  action: string;
  days: string;
}

export const EMPTY_AUDIT_FILTERS: AuditFilterValues = { entityType: "", entityId: "", actorId: "", action: "", days: "" };

const DAY_PRESETS = [
  { value: "1", label: "Last 24 hours" },
  { value: "7", label: "Last 7 days" },
  { value: "30", label: "Last 30 days" },
  { value: "90", label: "Last 90 days" },
];

/** Keyed by the parent on `value` (see call sites below) so an
 * external change — Reset, switching source — remounts with a fresh
 * initial draft instead of syncing via an effect (this session's
 * established fix for "reset local state when a prop changes"; see
 * `TeamFormDialog`). */
function DebouncedTextField({ id, label, value, onCommit }: { id: string; label: string; value: string; onCommit: (value: string) => void }) {
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (draft !== value) onCommit(draft);
    }, 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft]);

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} value={draft} onChange={(event) => setDraft(event.target.value)} className="w-48" />
    </div>
  );
}

/**
 * Real filters, genuinely different per source (see `AuditEventSearchParams`'s
 * own docstring) — never a universal control set. `integrations` has no
 * filter beyond the fixed organization scope, so it shows a plain note
 * instead of empty, disabled-looking controls.
 */
export function AuditFilters({
  source,
  values,
  onChange,
  onReset,
}: {
  source: AuditSourceValue;
  values: AuditFilterValues;
  onChange: (values: AuditFilterValues) => void;
  onReset: () => void;
}) {
  const activeFilterCount = Object.values(values).filter(Boolean).length;

  if (source === "integrations") {
    return <p className="text-muted-foreground text-sm">This source has no additional filters — only organization scope.</p>;
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      {source === "compliance" && (
        <>
          <DebouncedTextField key={`entityType:${values.entityType}`} id="audit-entity-type" label="Entity type" value={values.entityType} onCommit={(entityType) => onChange({ ...values, entityType })} />
          <DebouncedTextField key={`entityId:${values.entityId}`} id="audit-entity-id" label="Entity ID" value={values.entityId} onCommit={(entityId) => onChange({ ...values, entityId })} />
          <DebouncedTextField key={`actorId:${values.actorId}`} id="audit-actor-id" label="Actor ID" value={values.actorId} onCommit={(actorId) => onChange({ ...values, actorId })} />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="audit-days">Date range</Label>
            <Select id="audit-days" value={values.days} onChange={(event) => onChange({ ...values, days: event.target.value })} className="w-40">
              <option value="">Last 90 days (default)</option>
              {DAY_PRESETS.map((preset) => (
                <option key={preset.value} value={preset.value}>
                  {preset.label}
                </option>
              ))}
            </Select>
          </div>
        </>
      )}

      {source === "notifications" && (
        <>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="audit-action">Action</Label>
            <Select id="audit-action" value={values.action} onChange={(event) => onChange({ ...values, action: event.target.value })} className="w-56">
              <option value="">All actions</option>
              {NOTIFICATIONS_AUDIT_ACTIONS.map((action) => (
                <option key={action} value={action}>
                  {formatActionLabel(action)}
                </option>
              ))}
            </Select>
          </div>
          <DebouncedTextField key={`entityId:${values.entityId}`} id="audit-entity-id" label="Entity ID" value={values.entityId} onCommit={(entityId) => onChange({ ...values, entityId })} />
          <DebouncedTextField key={`actorId:${values.actorId}`} id="audit-actor-id" label="Actor ID" value={values.actorId} onCommit={(actorId) => onChange({ ...values, actorId })} />
        </>
      )}

      {activeFilterCount > 0 && (
        <Button variant="ghost" onClick={onReset} className="gap-1.5">
          <X className="size-4" aria-hidden="true" />
          Reset
          <Badge variant="outline">{activeFilterCount}</Badge>
        </Button>
      )}
    </div>
  );
}
