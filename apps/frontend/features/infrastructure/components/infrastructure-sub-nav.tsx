"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/utils/cn";

const ITEMS = [
  { href: "/infrastructure", label: "Overview" },
  { href: "/infrastructure/assets", label: "Assets" },
  { href: "/infrastructure/groups", label: "Groups" },
];

/** Mirrors `@/features/monitoring/components/monitoring-sub-nav.tsx` —
 * real routes, not registered in the primary sidebar
 * (`showInNav: false`), reachable from here, the command palette, and
 * Dashboard's/Monitoring's own cross-links instead. */
export function InfrastructureSubNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Infrastructure sections" className="border-border flex gap-1 border-b">
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
