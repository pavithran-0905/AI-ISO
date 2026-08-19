"use client";

import { usePathname } from "next/navigation";

import { SettingsLayout } from "@/layouts/settings-layout";
import { useSession } from "@/auth/session";
import { ApiKeysSection } from "@/features/settings/components/api-keys-section";
import { DevicesSection } from "@/features/settings/components/devices-section";
import { MfaSection } from "@/features/settings/components/mfa-section";
import { PasswordSection } from "@/features/settings/components/password-section";
import { renderSettingsNavLink } from "@/features/settings/components/settings-nav-link";
import { SessionsSection } from "@/features/settings/components/sessions-section";
import { useSettingsNavItems } from "@/features/settings/lib/nav-items";

/** Security — `/settings/security`. Every section (MFA, API keys,
 * devices, sessions, password) queries and mutates independently. */
export function SecurityPage() {
  const pathname = usePathname();
  const navItems = useSettingsNavItems();
  const { user } = useSession();

  return (
    <SettingsLayout title="Security" navItems={navItems} activeHref={pathname} renderNavLink={renderSettingsNavLink}>
      <div className="flex flex-col gap-6">
        <MfaSection mfaEnabled={user?.mfaEnabled ?? false} />
        <ApiKeysSection />
        <DevicesSection />
        <SessionsSection />
        <PasswordSection email={user?.email ?? null} />
      </div>
    </SettingsLayout>
  );
}
