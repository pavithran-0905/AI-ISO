"use client";

import { usePathname } from "next/navigation";

import { SettingsLayout } from "@/layouts/settings-layout";
import { SectionState } from "@/features/dashboard/components/section-state";
import { DisplayPreferencesSection } from "@/features/settings/components/display-preferences-section";
import { IdentityForm } from "@/features/settings/components/identity-form";
import { PreferencesForm } from "@/features/settings/components/preferences-form";
import { ProfileForm } from "@/features/settings/components/profile-form";
import { renderSettingsNavLink } from "@/features/settings/components/settings-nav-link";
import { useUserPreferences, useUserProfile } from "@/features/settings/hooks/use-preferences";
import { useSettingsNavItems } from "@/features/settings/lib/nav-items";

/**
 * My Preferences — `/settings` (§6). Every section queries and saves
 * independently (§36): a slow/failed `/users/profile` never blocks
 * `/users/preferences` or the local display controls from rendering.
 */
export function PreferencesPage() {
  const pathname = usePathname();
  const navItems = useSettingsNavItems();
  const preferencesQuery = useUserPreferences();
  const profileQuery = useUserProfile();

  return (
    <SettingsLayout title="My Preferences" navItems={navItems} activeHref={pathname} renderNavLink={renderSettingsNavLink}>
      <div className="flex flex-col gap-6">
        <IdentityForm />

        <SectionState isLoading={profileQuery.isLoading} isError={profileQuery.isError} error={profileQuery.error} onRetry={() => profileQuery.refetch()}>
          {profileQuery.data && <ProfileForm profile={profileQuery.data} />}
        </SectionState>

        <SectionState
          isLoading={preferencesQuery.isLoading}
          isError={preferencesQuery.isError}
          error={preferencesQuery.error}
          onRetry={() => preferencesQuery.refetch()}
        >
          {preferencesQuery.data && <PreferencesForm preferences={preferencesQuery.data} />}
        </SectionState>

        <DisplayPreferencesSection />
      </div>
    </SettingsLayout>
  );
}
