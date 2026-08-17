"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { getBreadcrumbTrail } from "@/lib/route-registry";
import { cn } from "@/utils/cn";

/**
 * The breadcrumb trail (docs/frontend Prompt 003 §12), derived from
 * `@/lib/route-registry` — no page defines its own breadcrumb. Renders
 * nothing for an unregistered path (e.g. a 404) rather than a broken
 * trail.
 */
export function Breadcrumbs() {
  const pathname = usePathname();
  const trail = getBreadcrumbTrail(pathname);

  if (trail.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm">
      <ol className="flex items-center gap-1.5">
        {trail.map((route, index) => {
          const isCurrent = index === trail.length - 1;
          return (
            <li key={route.id} className="flex items-center gap-1.5">
              {index > 0 && <ChevronRight className="text-muted-foreground size-3.5" aria-hidden="true" />}
              {isCurrent ? (
                <span aria-current="page" className="text-foreground max-w-48 truncate font-medium">
                  {route.breadcrumb}
                </span>
              ) : (
                <Link
                  href={route.path}
                  className={cn("text-muted-foreground hover:text-foreground max-w-48 truncate transition-colors")}
                >
                  {route.breadcrumb}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
