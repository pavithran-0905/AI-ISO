"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useSession } from "@/auth/session";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { Popover } from "@/components/overlays/popover";
import { IconButton } from "@/components/ui/icon-button";
import { formatLabel, STATUS_TONES } from "@/features/notifications/lib/format";
import { useRecentNotifications } from "@/features/notifications/hooks/use-notifications";
import { typography } from "@/lib/typography";
import { useSelectedOrganization } from "@/organization/use-organizations";

/**
 * The notification bell (docs/frontend Prompt 003 §17, wired up for
 * real in Prompt 016). **No unread-count route exists** on
 * `notification-center-service` (confirmed absent — see
 * `useRecentNotifications`' own docstring), so this never shows a
 * number: only a plain dot when the most recently fetched bounded page
 * contains at least one unread item. `GET /notifications` requires no
 * authentication at all — see `docs/frontend/developer-guide/notifications.md`.
 */
export function NotificationArea() {
  const [open, setOpen] = useState(false);
  const { userId } = useSession();
  const { selectedOrganizationId } = useSelectedOrganization();
  const query = useRecentNotifications(selectedOrganizationId, userId);

  const items = query.data?.items ?? [];
  const hasUnread = items.some((item) => item.readAt === null);

  return (
    <Popover
      open={open}
      onClose={() => setOpen(false)}
      align="end"
      trigger={
        <span className="relative inline-flex">
          <IconButton
            icon={Bell}
            aria-label={hasUnread ? "Notifications, unread items" : "Notifications"}
            variant="ghost"
            onClick={() => setOpen((value) => !value)}
          />
          {hasUnread && (
            <span aria-hidden="true" className="bg-danger absolute -top-0.5 -right-0.5 size-2.5 rounded-full" />
          )}
        </span>
      }
    >
      <div className="flex w-80 flex-col gap-2">
        <div className="flex items-center justify-between">
          <p className={typography.cardTitle}>Notifications</p>
          <Link href="/notifications" className="text-primary text-xs hover:underline" onClick={() => setOpen(false)}>
            View all
          </Link>
        </div>

        {query.isLoading && <p className="text-muted-foreground p-4 text-center text-sm">Loading…</p>}
        {query.isError && <p className="text-muted-foreground p-4 text-center text-sm">Unable to load notifications right now.</p>}
        {query.data && items.length === 0 && (
          <EmptyState title="You're all caught up" description="No notifications yet." className="p-4" />
        )}
        {items.length > 0 && (
          <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto">
            {items.map((notification) => (
              <li key={notification.id}>
                <Link
                  href={`/notifications/${notification.id}`}
                  onClick={() => setOpen(false)}
                  className="hover:bg-muted focus-visible:ring-ring flex flex-col gap-0.5 rounded-md p-2 text-sm focus-visible:ring-2 focus-visible:outline-none"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={notification.readAt === null ? "font-semibold" : ""}>
                      {notification.subject ?? notification.body.slice(0, 60)}
                    </span>
                    <StatusBadge tone={STATUS_TONES[notification.status]} label={formatLabel(notification.status)} />
                  </div>
                  <span className="text-muted-foreground text-xs">
                    <time dateTime={notification.createdAt}>{new Date(notification.createdAt).toLocaleString()}</time>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Popover>
  );
}
