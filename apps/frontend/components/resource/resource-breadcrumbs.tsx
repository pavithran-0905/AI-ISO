import { ChevronRight } from "lucide-react";
import Link from "next/link";

export interface ResourceBreadcrumbEntry {
  label: string;
  href?: string;
}

/**
 * A real, pre-existing gap this component fixes: the shell's own
 * `Breadcrumbs` (`components/navigation/breadcrumbs.tsx`) resolves a
 * trail by an *exact* pathname match against `lib/route-registry.ts`
 * — a dynamic detail route (`/infrastructure/assets/{id}`) was never
 * registered there (confirmed: no dynamic `[id]` route is, matching
 * every other detail page's own established convention) and so never
 * matched, meaning every resource detail page has shown no breadcrumb
 * trail at all until now. `ResourceBreadcrumbs` takes an explicit
 * trail instead — its static ancestor entries still point at real
 * registered routes, only the final (current) entry is the resource's
 * own real name, which no registry entry could express anyway.
 */
export function ResourceBreadcrumbs({ trail }: { trail: ResourceBreadcrumbEntry[] }) {
  if (trail.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm">
      <ol className="flex items-center gap-1.5">
        {trail.map((entry, index) => {
          const isCurrent = index === trail.length - 1;
          return (
            <li key={`${entry.label}-${index}`} className="flex items-center gap-1.5">
              {index > 0 && <ChevronRight className="text-muted-foreground size-3.5" aria-hidden="true" />}
              {isCurrent || !entry.href ? (
                <span aria-current={isCurrent ? "page" : undefined} className="text-foreground max-w-48 truncate font-medium">
                  {entry.label}
                </span>
              ) : (
                <Link href={entry.href} className="text-muted-foreground hover:text-foreground max-w-48 truncate transition-colors">
                  {entry.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
