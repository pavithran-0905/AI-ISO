import Link from "next/link";

import type { SettingsNavItem } from "@/layouts/settings-layout";
import { cn } from "@/utils/cn";

/** The `renderNavLink` every `/settings/*` page passes to
 * `SettingsLayout` — a real `<Link>` (not a button + `router.push`),
 * so right-click/open-in-new-tab/middle-click all work correctly. */
export function renderSettingsNavLink(item: SettingsNavItem, isActive: boolean) {
  return (
    <Link
      href={item.href}
      aria-current={isActive ? "page" : undefined}
      className={cn(
        "block w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-colors",
        "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
        isActive ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {item.label}
    </Link>
  );
}
