"use client";

import Link from "next/link";

import { useSession } from "@/auth/session";
import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { DashboardWidget } from "@/features/dashboard/components/dashboard-widget";
import { useRecentNotifications } from "@/features/notifications/hooks/use-notifications";
import { isImportant } from "@/features/notifications/lib/format";
import type { Notification } from "@/features/notifications/types";
import { formatRelativeTime } from "@/lib/relative-time";

const MAX_VISIBLE = 4;

/**
 * Notification Summary (§20) — the exact bounded, most-recent page
 * `NotificationArea` (the shell bell, Prompt 016) already fetches for
 * this same user/organization (identical `queryKey`; React Query
 * dedupes, §36). **No total-unread count is shown** — no such route
 * exists (confirmed absent, see `useRecentNotifications`'s own
 * docstring); "Unread" here only ever means *this bounded page has an
 * item with `readAt === null`*, never a platform-wide total.
 */
export function NotificationSummaryWidget({ organizationId }: { organizationId: string }) {
  const { userId } = useSession();
  const query = useRecentNotifications(organizationId, userId);

  return (
    <DashboardWidget
      title="Notifications"
      description="Recent notifications addressed to you."
      action={{ label: "View notifications", href: "/notifications" }}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
    >
      {query.data && <NotificationSummaryList notifications={query.data.items} />}
    </DashboardWidget>
  );
}

function NotificationSummaryList({ notifications }: { notifications: Notification[] }) {
  if (notifications.length === 0) {
    return <EmptyState title="No recent notifications" description="Nothing addressed to you recently." />;
  }

  const important = notifications.filter((notification) => isImportant(notification.priority));
  const visible = (important.length > 0 ? important : notifications).slice(0, MAX_VISIBLE);

  return (
    <ul className="flex flex-col gap-1">
      {visible.map((notification) => (
        <li key={notification.id}>
          <Link
            href={`/notifications/${notification.id}`}
            className="hover:bg-muted focus-visible:ring-ring flex items-start justify-between gap-3 rounded-md p-2 focus-visible:ring-2 focus-visible:outline-none"
          >
            <div className="flex flex-col gap-0.5">
              <p className="line-clamp-1 text-sm font-medium">{notification.subject ?? notification.body}</p>
              <p className="text-muted-foreground text-xs">
                <time dateTime={notification.createdAt}>{formatRelativeTime(notification.createdAt)}</time>
              </p>
            </div>
            {notification.readAt === null && <StatusBadge tone="info" label="Unread" className="shrink-0" />}
          </Link>
        </li>
      ))}
    </ul>
  );
}
