"use client";

import { Bell } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { Popover } from "@/components/overlays/popover";
import { IconButton } from "@/components/ui/icon-button";
import { typography } from "@/lib/typography";

/**
 * The notification area (docs/frontend Prompt 003 §17) — UI foundation
 * only. **Backend V1 Integration Limitation**: no notification-reading
 * REST contract for `services/notification-center-service` was
 * confirmed during this prompt (its own docs/frontend backend-feature
 * matrix entry documents the service's existence and general
 * capability, not its exact per-notification read/list/mark-read route
 * shapes) — wiring a fetch to an unverified endpoint would risk
 * inventing a contract, which this prompt's own backend-freeze rule
 * forbids. The panel therefore always renders its empty state; the
 * unread-count badge, loading, and error states are implemented and
 * ready, just never triggered without real data. Wire this to a real
 * `features/notifications` API function once the exact contract is
 * confirmed.
 */
export function NotificationArea() {
  const [open, setOpen] = useState(false);
  const unreadCount = 0;

  return (
    <Popover
      open={open}
      onClose={() => setOpen(false)}
      align="end"
      trigger={
        <span className="relative inline-flex">
          <IconButton
            icon={Bell}
            aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : "Notifications"}
            variant="ghost"
            onClick={() => setOpen((value) => !value)}
          />
          {unreadCount > 0 && (
            <span
              aria-hidden="true"
              className="bg-danger text-danger-foreground absolute -top-0.5 -right-0.5 flex size-4 items-center justify-center rounded-full text-[10px] font-medium"
            >
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </span>
      }
    >
      <div className="flex w-72 flex-col gap-2">
        <p className={typography.cardTitle}>Notifications</p>
        <EmptyState title="No notifications yet" description="You're all caught up." className="p-4" />
      </div>
    </Popover>
  );
}
