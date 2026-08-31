import { SearchX } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

/**
 * §29's dedicated 404 resource state — distinct from `ErrorState`
 * (nothing is malfunctioning; the resource genuinely doesn't exist, or
 * doesn't exist for this caller — see §30 for the separate
 * permission-denied case, already handled generically by
 * `SectionState`'s own 403 branch). Never shown for a 5xx or a network
 * failure, only a confirmed backend 404.
 */
export function ResourceNotFound({
  resourceLabel,
  backHref,
  backLabel,
}: {
  resourceLabel: string;
  backHref: string;
  backLabel: string;
}) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center gap-3 p-12 text-center">
      <SearchX className="text-muted-foreground size-10" aria-hidden="true" />
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium">{resourceLabel} not found</p>
        <p className="text-muted-foreground text-sm">It may have been removed, or the link may be incorrect.</p>
      </div>
      <div className="flex items-center gap-2">
        <Link href={backHref} className={buttonVariants("outline")}>
          {backLabel}
        </Link>
        <Link href="/search" className={buttonVariants("ghost")}>
          Search
        </Link>
      </div>
    </div>
  );
}
