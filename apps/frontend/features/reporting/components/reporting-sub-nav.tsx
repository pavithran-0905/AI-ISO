"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/utils/cn";

const ITEMS = [
  { href: "/reporting", label: "Overview" },
  { href: "/reporting/reports", label: "Reports" },
  { href: "/reporting/templates", label: "Templates" },
  { href: "/reporting/schedules", label: "Scheduled Reports" },
  { href: "/reporting/history", label: "Generated Reports" },
  { href: "/reporting/archive", label: "Archive" },
];

/** Mirrors `@/features/monitoring/components/monitoring-sub-nav.tsx` and
 * `@/features/alerting/components/alerting-sub-nav.tsx` — real routes,
 * not registered in the primary sidebar (`showInNav: false`), reachable
 * from here, the command palette, and Dashboard's cross-link instead. */
export function ReportingSubNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Reporting sections" className="border-border flex flex-wrap gap-1 border-b">
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
