"use client";

import { Search, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { USER_STATUSES, type UserStatusValue } from "@/features/administration/types";

export interface UserFilterValues {
  query: string;
  status: UserStatusValue | "";
}

export const EMPTY_USER_FILTERS: UserFilterValues = { query: "", status: "" };

/** `POST /users/search`'s only two real, working filters — `query`
 * (free text over username/email/phone/display name) and `status`.
 * The request schema also accepts `department`/`tags`, but the
 * backend silently ignores both (confirmed by source inspection) —
 * not offered here, to avoid a control that does nothing. */
export function UserFilters({
  values,
  onChange,
  onReset,
}: {
  values: UserFilterValues;
  onChange: (values: UserFilterValues) => void;
  onReset: () => void;
}) {
  const activeFilterCount = [values.query, values.status].filter(Boolean).length;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex min-w-48 flex-1 flex-col gap-1.5">
        <Label htmlFor="user-search">Search</Label>
        <div className="relative">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
          <Input
            id="user-search"
            value={values.query}
            onChange={(event) => onChange({ ...values, query: event.target.value })}
            placeholder="Username, email, phone, or display name…"
            className="pl-9"
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="user-status-filter">Status</Label>
        <Select
          id="user-status-filter"
          value={values.status}
          onChange={(event) => onChange({ ...values, status: event.target.value as UserStatusValue | "" })}
          className="w-40"
        >
          <option value="">All statuses</option>
          {USER_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
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
