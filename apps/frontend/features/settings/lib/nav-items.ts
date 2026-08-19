import type { SettingsNavItem } from "@/layouts/settings-layout";
import { usePermissions } from "@/permissions/hooks";

const BASE_ITEMS: SettingsNavItem[] = [
  { href: "/settings", label: "My Preferences" },
  { href: "/settings/security", label: "Security" },
  { href: "/settings/organization", label: "Organization" },
  { href: "/settings/projects", label: "Projects" },
  { href: "/settings/integrations", label: "Integrations" },
  { href: "/settings/notifications", label: "Notifications" },
  { href: "/settings/ai", label: "AI" },
];

const SYSTEM_ITEM: SettingsNavItem = { href: "/settings/system", label: "System" };

/**
 * Organization/Projects show read-only to any member (their own real
 * `GET` routes require only membership) — only their own *edit*
 * controls are gated per-section. System is hidden from the nav
 * entirely for non-administrators: its `GET` routes technically allow
 * any authenticated user (confirmed absent of a role check on reads),
 * but showing platform-wide tenant/settings/feature-flag data to an
 * ordinary viewer would violate §5/§7's intent even though the
 * backend itself doesn't enforce it — a deliberate frontend-side
 * tightening, not a fabricated permission. See the developer guide.
 */
export function useSettingsNavItems(): SettingsNavItem[] {
  const { isAdministrative } = usePermissions();
  return isAdministrative ? [...BASE_ITEMS, SYSTEM_ITEM] : BASE_ITEMS;
}
