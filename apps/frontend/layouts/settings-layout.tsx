"use client";

import { useEffect } from "react";

import { typography } from "@/lib/typography";
import { cn } from "@/utils/cn";

export interface SettingsNavItem {
  href: string;
  label: string;
}

/**
 * Settings Layout (docs/frontend Prompt 001 §16, standardized by
 * Prompt 003 §32) — sidebar navigation, a page title, and a save/cancel
 * action area, for future settings/admin sections. Takes plain
 * `href`/`label` items and an `activeHref` rather than owning routing
 * itself, so it works the same whether the caller uses Next's `<Link>`
 * or a plain anchor in a test.
 *
 * `hasUnsavedChanges` drives the one piece of unsaved-change handling
 * that belongs at this generic-framework level — warning on tab
 * close/refresh via `beforeunload`. Blocking in-app navigation away
 * from a dirty form is feature-specific (it needs to know what "leave"
 * means for that section) and stays out of scope here.
 */
export function SettingsLayout({
  title,
  navItems,
  activeHref,
  renderNavLink,
  actions,
  hasUnsavedChanges = false,
  children,
}: {
  title: string;
  navItems: SettingsNavItem[];
  activeHref: string;
  renderNavLink: (item: SettingsNavItem, isActive: boolean) => React.ReactNode;
  /** The save/cancel action area, rendered next to the page title. */
  actions?: React.ReactNode;
  hasUnsavedChanges?: boolean;
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    function handleBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

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
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h1 className={typography.pageTitle}>{title}</h1>
            {hasUnsavedChanges && (
              <span className="text-warning bg-warning/10 rounded-full px-2 py-0.5 text-xs font-medium">
                Unsaved changes
              </span>
            )}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
        {children}
      </div>
    </div>
  );
}
