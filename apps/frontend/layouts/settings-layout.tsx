import { cn } from "@/utils/cn";

export interface SettingsNavItem {
  href: string;
  label: string;
}

/**
 * Settings Layout (docs/frontend Prompt 001 §16) — sidebar navigation
 * plus content, for future settings/admin sections. Takes plain
 * `href`/`label` items and an `activeHref` rather than owning routing
 * itself, so it works the same whether the caller uses Next's `<Link>`
 * or a plain anchor in a test.
 */
export function SettingsLayout({
  navItems,
  activeHref,
  renderNavLink,
  children,
}: {
  navItems: SettingsNavItem[];
  activeHref: string;
  renderNavLink: (item: SettingsNavItem, isActive: boolean) => React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-full flex-col gap-6 md:flex-row">
      <nav aria-label="Settings" className="shrink-0 md:w-56">
        <ul className="flex flex-row gap-1 overflow-x-auto md:flex-col md:overflow-visible">
          {navItems.map((item) => (
            <li key={item.href} className={cn("shrink-0")}>
              {renderNavLink(item, item.href === activeHref)}
            </li>
          ))}
        </ul>
      </nav>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
