"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/utils/cn";

const ITEMS = [
  { href: "/intelligence", label: "Overview" },
  { href: "/intelligence/assistant", label: "AI Assistant" },
  { href: "/intelligence/knowledge", label: "Knowledge" },
  { href: "/intelligence/recommendations", label: "Recommendations" },
  { href: "/intelligence/reports", label: "AI Reports" },
  { href: "/intelligence/analytics", label: "Analytics" },
  { href: "/intelligence/prompts", label: "Prompts" },
];

/** Mirrors `@/features/reporting/components/reporting-sub-nav.tsx` —
 * real routes, not registered in the primary sidebar
 * (`showInNav: false`), reachable from here, the command palette, and
 * cross-module "Ask AI" links instead. */
export function AiAssistantSubNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Intelligence sections" className="border-border flex flex-wrap gap-1 border-b">
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
