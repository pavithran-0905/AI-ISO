"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/utils/cn";

const ITEMS = [
  { href: "/audit", label: "Overview" },
  { href: "/audit/activity", label: "Activity" },
];

/** Mirrors `@/features/administration/components/administration-sub-nav.tsx`.
 * Only two entries — the recommended IA's "Activity"/"Audit Events"/
 * "Event Detail" collapse into the single Activity page (table/timeline
 * switch over one dataset; detail is an in-page drawer, not a route —
 * see `features/audit/components/event-detail-drawer.tsx`). */
export function AuditSubNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Audit & Activity sections" className="border-border flex gap-1 border-b">
      {ITEMS.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
              active ? "border-primary text-foreground" : "text-muted-foreground hover:text-foreground border-transparent",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
