"use client";

import { Search, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { ALERT_SEVERITIES, ALERT_STATUSES, type AlertSeverity, type AlertStatusValue } from "@/features/alerting/types";

export interface AlertFilterValues {
  query: string;
  status: AlertStatusValue | "";
  severity: AlertSeverity | "";
}

export const EMPTY_ALERT_FILTERS: AlertFilterValues = { query: "", status: "", severity: "" };

/**
 * `status`/`severity` are real `GET /alerts` query params (server-side).
 * `query` is a client-side text search over title/message/source —
 * honest here specifically because `GET /alerts` returns its full,
 * unpaginated result for the given status/severity filter, so there is
 * no hidden remainder a client-side search could silently miss (unlike
 * a bounded scan over a paginated endpoint).
 */
export function AlertFilters({
  values,
  onChange,
  onReset,
}: {
  values: AlertFilterValues;
  onChange: (values: AlertFilterValues) => void;
  onReset: () => void;
}) {
  const activeFilterCount = [values.query, values.status, values.severity].filter(Boolean).length;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex min-w-48 flex-1 flex-col gap-1.5">
        <Label htmlFor="alert-search">Search</Label>
        <div className="relative">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
          <Input
            id="alert-search"
            value={values.query}
            onChange={(event) => onChange({ ...values, query: event.target.value })}
            placeholder="Title, message, source…"
            className="pl-9"
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="alert-status-filter">Status</Label>
        <Select
          id="alert-status-filter"
          value={values.status}
          onChange={(event) => onChange({ ...values, status: event.target.value as AlertStatusValue | "" })}
          className="w-40"
        >
          <option value="">All statuses</option>
          {ALERT_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="alert-severity-filter">Severity</Label>
        <Select
          id="alert-severity-filter"
          value={values.severity}
          onChange={(event) => onChange({ ...values, severity: event.target.value as AlertSeverity | "" })}
          className="w-40"
        >
          <option value="">All severities</option>
          {ALERT_SEVERITIES.map((severity) => (
            <option key={severity} value={severity}>
              {severity}
            </option>
          ))}
        </Select>
      </div>

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
