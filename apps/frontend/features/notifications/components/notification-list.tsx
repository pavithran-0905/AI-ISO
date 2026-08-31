"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Button } from "@/components/ui/button";
import { categoryLabel, formatLabel, PRIORITY_TONES, STATUS_TONES } from "@/features/notifications/lib/format";
import type { Notification, NotificationSearchResult } from "@/features/notifications/types";
import { useTableDensityStore } from "@/state/table-density-store";
import { cn } from "@/utils/cn";

/**
 * §7's notification-center list. `result` carries the real, server-
 * paginated page; `items` is what's actually rendered — the parent
 * applies the "Unread"/"Important" quick view to `result.items`
 * client-side before passing it here, so this component only ever
 * renders, never decides what counts as unread or important (see the
 * developer guide's `NotificationQuickView` section).
 */
export function NotificationList({
  result,
  items,
  onPageChange,
}: {
  result: NotificationSearchResult;
  items: Notification[];
  onPageChange: (offset: number) => void;
}) {
  const density = useTableDensityStore((state) => state.density);
  const cellPadding = density === "compact" ? "px-3 py-1.5" : "px-3 py-3";
  const page = Math.floor(result.offset / result.limit) + 1;

  return (
    <div className="flex flex-col gap-3">
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-border border-b">
              <th scope="col" className={cn(cellPadding, "font-medium")}>Subject</th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>Category</th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>Priority</th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>Source</th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>Status</th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>Received</th>
            </tr>
          </thead>
          <tbody>
            {items.map((notification) => (
              <tr key={notification.id} className={cn("border-border hover:bg-muted/50 border-b last:border-0", notification.readAt === null && "font-medium")}>
                <td className={cellPadding}>
                  <Link
                    href={`/notifications/${notification.id}`}
                    className="focus-visible:ring-ring rounded hover:underline focus-visible:ring-2 focus-visible:outline-none"
                  >
                    {notification.subject ?? notification.body.slice(0, 60)}
                  </Link>
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{categoryLabel(notification.category)}</td>
                <td className={cellPadding}>
                  <StatusBadge tone={PRIORITY_TONES[notification.priority]} label={formatLabel(notification.priority)} />
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{notification.sourceService}</td>
                <td className={cellPadding}>
                  <StatusBadge tone={STATUS_TONES[notification.status]} label={formatLabel(notification.status)} />
                </td>
                <td className={cn(cellPadding, "text-muted-foreground whitespace-nowrap")}>
                  <time dateTime={notification.createdAt}>{new Date(notification.createdAt).toLocaleString()}</time>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="flex flex-col gap-2 md:hidden">
        {items.map((notification) => (
          <li key={notification.id}>
            <Link href={`/notifications/${notification.id}`} className="block">
              <Card className="hover:border-muted-foreground/50 transition-colors">
                <CardContent className="flex flex-col gap-1 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className={cn("text-sm", notification.readAt === null && "font-semibold")}>
                      {notification.subject ?? notification.body.slice(0, 60)}
                    </p>
                    <StatusBadge tone={STATUS_TONES[notification.status]} label={formatLabel(notification.status)} />
                  </div>
                  <p className="text-muted-foreground text-xs">
                    {categoryLabel(notification.category)} · {notification.sourceService}
                  </p>
                  <p className="text-muted-foreground text-xs">
                    <time dateTime={notification.createdAt}>{new Date(notification.createdAt).toLocaleString()}</time>
                  </p>
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>

      <div className="flex items-center justify-between gap-3 text-sm">
        <p className="text-muted-foreground">
          Page {page} · {items.length === result.items.length ? `${items.length} shown` : `${items.length} of ${result.items.length} loaded shown`}
        </p>
        <div className="flex items-center gap-2">
          <Button variant="outline" disabled={result.offset <= 0} onClick={() => onPageChange(Math.max(0, result.offset - result.limit))}>
            Previous
          </Button>
          <Button variant="outline" disabled={!result.hasMore} onClick={() => onPageChange(result.offset + result.limit)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
