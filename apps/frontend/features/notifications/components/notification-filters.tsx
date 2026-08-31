"use client";

import { X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { formatLabel } from "@/features/notifications/lib/format";
import { NOTIFICATION_CATEGORIES, NOTIFICATION_STATUSES } from "@/features/notifications/types";

export interface NotificationFilterValues {
  category: string;
  status: string;
}

export const EMPTY_NOTIFICATION_FILTERS: NotificationFilterValues = { category: "", status: "" };

/** The two real filters `GET /notifications` supports —
 * `category`/`status`, each exactly one value. There is no
 * "unread"-shaped status value; that's a separate, client-side quick
 * view (`NotificationQuickView`), not offered here. */
export function NotificationFilters({
  values,
  onChange,
  onReset,
}: {
  values: NotificationFilterValues;
  onChange: (values: NotificationFilterValues) => void;
  onReset: () => void;
}) {
  const activeFilterCount = [values.category, values.status].filter(Boolean).length;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="notification-category">Category</Label>
        <Select id="notification-category" value={values.category} onChange={(event) => onChange({ ...values, category: event.target.value })} className="w-48">
          <option value="">All categories</option>
          {NOTIFICATION_CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {formatLabel(category)}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="notification-status">Status</Label>
        <Select id="notification-status" value={values.status} onChange={(event) => onChange({ ...values, status: event.target.value })} className="w-40">
          <option value="">All statuses</option>
          {NOTIFICATION_STATUSES.map((status) => (
            <option key={status} value={status}>
              {formatLabel(status)}
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
