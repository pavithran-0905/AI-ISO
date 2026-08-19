"use client";

import { usePathname } from "next/navigation";

import { SettingsLayout } from "@/layouts/settings-layout";
import { EmptyState } from "@/components/feedback/empty-state";
import { renderSettingsNavLink } from "@/features/settings/components/settings-nav-link";
import { useSettingsNavItems } from "@/features/settings/lib/nav-items";

/**
 * AI — `/settings/ai` (§16). `ai-assistant-service` exposes no
 * preference/settings endpoint of any kind (confirmed absent by
 * direct source inspection of every router in that service) — nothing
 * to build here. Shown explicitly with the reason, rather than
 * silently omitting the nav item, matching this session's established
 * pattern for a documented gap (e.g. Monitoring's metrics-deferred
 * section, Infrastructure's related-alerts section).
 */
export function AiSettingsPage() {
  const pathname = usePathname();
  const navItems = useSettingsNavItems();

  return (
    <SettingsLayout title="AI" navItems={navItems} activeHref={pathname} renderNavLink={renderSettingsNavLink}>
      <EmptyState
        title="AI preferences aren't configurable yet"
        description="AI-IOS's AI Assistant backend doesn't expose any preference or settings endpoint today — there's genuinely nothing to configure from this page yet."
      />
    </SettingsLayout>
  );
}
