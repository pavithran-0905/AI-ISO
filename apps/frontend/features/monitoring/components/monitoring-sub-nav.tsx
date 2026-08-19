"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/utils/cn";

const ITEMS = [
  { href: "/monitoring", label: "Overview" },
  { href: "/monitoring/services", label: "Services" },
  { href: "/monitoring/events", label: "Events" },
];

/**
 * Real navigable sub-routes styled as tabs (not the ARIA `Tabs` widget
 * — that's for panel-switching within one page/URL; these are
 * distinct, shareable routes, which §14 requires for filter state).
 * Not registered in the primary sidebar (`showInNav: false` in
 * `lib/route-registry.ts`) to avoid a fourth nesting level the shell
 * doesn't support yet — reachable from here, the command palette, and
 * Dashboard cross-links instead.
 */
export function MonitoringSubNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Monitoring sections" className="border-border flex gap-1 border-b">
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
