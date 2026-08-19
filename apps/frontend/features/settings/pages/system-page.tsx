"use client";

import { usePathname } from "next/navigation";

import { SettingsLayout } from "@/layouts/settings-layout";
import { FeatureFlagsSection } from "@/features/settings/components/feature-flags-section";
import { PlatformSettingsSection } from "@/features/settings/components/platform-settings-section";
import { renderSettingsNavLink } from "@/features/settings/components/settings-nav-link";
import { SystemJobsSection } from "@/features/settings/components/system-jobs-section";
import { SystemObservabilitySection } from "@/features/settings/components/system-observability-section";
import { SystemOverviewSection } from "@/features/settings/components/system-overview-section";
import { useSettingsNavItems } from "@/features/settings/lib/nav-items";

/**
 * System — `/settings/system`. Only reachable from the nav for
 * administrators (`nav-items.ts`) — this page itself performs no
 * additional gate, since the backend's own read routes require only a
 * valid JWT anyway (confirmed). Every mutation here will genuinely
 * 403 today: `administration-portal-service` requires a `roles` array
 * JWT claim this platform's tokens never populate at login (the
 * documented Prompt 001 gap, in its most consequential form yet) —
 * see the developer guide. Tenant management is deliberately not
 * built here — real, but cross-organization operator tooling, not a
 * per-organization Settings concern.
 */
export function SystemPage() {
  const pathname = usePathname();
  const navItems = useSettingsNavItems();

  return (
    <SettingsLayout title="System" navItems={navItems} activeHref={pathname} renderNavLink={renderSettingsNavLink}>
      <div className="flex flex-col gap-6">
        <SystemOverviewSection />
        <PlatformSettingsSection />
        <FeatureFlagsSection />
        <SystemJobsSection />
        <SystemObservabilitySection />
      </div>
    </SettingsLayout>
  );
}
