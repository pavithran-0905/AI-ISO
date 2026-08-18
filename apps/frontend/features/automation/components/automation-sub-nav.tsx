"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/utils/cn";

/** Only three sections, because only three are backed by real V1
 * endpoints (§3: "only create sections backed by V1"). The IA §3
 * recommends Schedules and Targets too — both are omitted deliberately:
 * `automation-service` has full schedule and target models, services,
 * and repositories, but **zero routes** for either, and its cron engine
 * is never started. See
 * `docs/frontend/backend-v1-integration-limitations.md`. */
const ITEMS = [
  { href: "/automation", label: "Overview" },
  { href: "/automation/automations", label: "Automations" },
  { href: "/automation/executions", label: "Executions" },
];

export function AutomationSubNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Automation sections" className="border-border flex flex-wrap gap-1 border-b">
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
