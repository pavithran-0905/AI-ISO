"use client";

import { ChevronDown, ChevronRight, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { Badge } from "@/components/ui/badge";
import { IconButton } from "@/components/ui/icon-button";
import { Tooltip } from "@/components/overlays/tooltip";
import { getNavGroups, type NavGroupEntry, type RouteMeta } from "@/lib/route-registry";
import { usePermissions } from "@/permissions/hooks";
import { useMobileNavStore } from "@/state/mobile-nav-store";
import { useSidebarStore } from "@/state/sidebar-store";
import { cn } from "@/utils/cn";

const ITEM_CLASS =
  "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none";

/**
 * The primary navigation (docs/frontend Prompt 003 §7-§11). Renders
 * two structures sharing the same route data and group logic:
 *
 * - A persistent, collapsible sidebar (`md:` and up) — §11's "Desktop:
 *   persistent sidebar" and "Tablet: collapsible/sidebar drawer
 *   behaviour" (the existing icon-collapse mode covers the tablet
 *   range; Tailwind's stock breakpoints don't distinguish tablet from
 *   desktop any finer than that without inventing a custom one).
 * - A slide-over drawer (below `md`) — §11's "Narrow viewport:
 *   navigation becomes an accessible drawer/sheet," never a shrunk
 *   copy of the desktop sidebar. Opened via the header's hamburger
 *   trigger (`useMobileNavStore`), built on the same native `<dialog>`
 *   primitive as `Drawer`/`Dialog` for a real focus trap and
 *   Escape-to-close, and closes itself when a link is chosen so the
 *   content underneath is immediately visible.
 *
 * A single-route group (`overview` → just `Dashboard`) renders as a
 * flat top-level link using the route's own icon; a multi-route group
 * renders as an expandable header (the group's own icon) with indented
 * sub-items — matching §7's own example exactly. `"planned"` routes
 * render disabled with a `Badge`, never as a real link (§3: no fake
 * pages).
 */
export function PrimaryNavigation() {
  const pathname = usePathname();
  const collapsed = useSidebarStore((state) => state.collapsed);
  const toggleSidebar = useSidebarStore((state) => state.toggle);
  const collapsedGroups = useSidebarStore((state) => state.collapsedGroups);
  const toggleGroup = useSidebarStore((state) => state.toggleGroup);
  const mobileOpen = useMobileNavStore((state) => state.open);
  const hideMobileNav = useMobileNavStore((state) => state.hide);
  const { role } = usePermissions();
  const dialogRef = useRef<HTMLDialogElement>(null);

  const groups = getNavGroups().map((entry) => ({
    ...entry,
    routes: entry.routes.filter((route) => route.roles === null || (role !== null && route.roles.includes(role))),
  }));

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (mobileOpen && !dialog.open) dialog.showModal();
    if (!mobileOpen && dialog.open) dialog.close();
  }, [mobileOpen]);

  return (
    <>
      <nav
        aria-label="Primary"
        className={cn(
          "border-border bg-surface hidden shrink-0 flex-col gap-1 border-r py-3 transition-[width] duration-200 md:flex",
          collapsed ? "w-14 items-center px-2" : "w-60 px-3",
        )}
      >
        <div className={cn("flex", collapsed ? "justify-center" : "justify-end")}>
          <IconButton
            icon={collapsed ? PanelLeftOpen : PanelLeftClose}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            variant="ghost"
            onClick={toggleSidebar}
          />
        </div>

        <div className="flex flex-1 flex-col gap-1 overflow-y-auto">
          {groups.map((entry) => (
            <NavGroupSection
              key={entry.group}
              entry={entry}
              collapsed={collapsed}
              groupCollapsed={collapsedGroups[entry.group] ?? false}
              onToggleGroup={() => toggleGroup(entry.group)}
              pathname={pathname}
            />
          ))}
        </div>
      </nav>

      <dialog
        ref={dialogRef}
        onClose={hideMobileNav}
        onCancel={hideMobileNav}
        aria-label="Navigation"
        className={cn(
          "bg-surface text-foreground fixed inset-y-0 left-0 m-0 flex h-full max-h-none w-full max-w-64 flex-col",
          "border-r border-border p-3 shadow-elevation-3",
          "backdrop:bg-foreground/40",
          "motion-safe:open:animate-drawer-in md:hidden",
        )}
        onClick={(event) => {
          if (event.target === dialogRef.current) hideMobileNav();
        }}
      >
        <div className="flex flex-1 flex-col gap-1 overflow-y-auto">
          {groups.map((entry) => (
            <NavGroupSection
              key={entry.group}
              entry={entry}
              collapsed={false}
              groupCollapsed={collapsedGroups[entry.group] ?? false}
              onToggleGroup={() => toggleGroup(entry.group)}
              pathname={pathname}
              onNavigate={hideMobileNav}
            />
          ))}
        </div>
      </dialog>
    </>
  );
}

function NavGroupSection({
  entry,
  collapsed,
  groupCollapsed,
  onToggleGroup,
  pathname,
  onNavigate,
}: {
  entry: NavGroupEntry;
  collapsed: boolean;
  groupCollapsed: boolean;
  onToggleGroup: () => void;
  pathname: string;
  onNavigate?: () => void;
}) {
  if (entry.routes.length === 1) {
    return (
      <NavLink
        route={entry.routes[0]}
        icon={entry.routes[0].icon ?? entry.icon}
        collapsed={collapsed}
        active={pathname === entry.routes[0].path}
        onNavigate={onNavigate}
      />
    );
  }

  const GroupIcon = entry.icon;

  return (
    <div>
      {collapsed ? (
        <Tooltip label={entry.label} side="right">
          <div className={cn(ITEM_CLASS, "text-muted-foreground justify-center")}>
            <GroupIcon className="size-5" aria-hidden="true" />
          </div>
        </Tooltip>
      ) : (
        <button
          type="button"
          onClick={onToggleGroup}
          aria-expanded={!groupCollapsed}
          className={cn(ITEM_CLASS, "text-muted-foreground hover:bg-muted hover:text-foreground w-full justify-between")}
        >
          <span className="flex items-center gap-2">
            <GroupIcon className="size-5" aria-hidden="true" />
            {entry.label}
          </span>
          {groupCollapsed ? (
            <ChevronRight className="size-4" aria-hidden="true" />
          ) : (
            <ChevronDown className="size-4" aria-hidden="true" />
          )}
        </button>
      )}
      {!collapsed && !groupCollapsed && (
        <div className="flex flex-col gap-0.5 pl-4">
          {entry.routes.map((route) => (
            <NavLink
              key={route.id}
              route={route}
              icon={null}
              collapsed={false}
              active={pathname === route.path}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function NavLink({
  route,
  icon: Icon,
  collapsed,
  active,
  onNavigate,
}: {
  route: RouteMeta;
  icon: RouteMeta["icon"];
  collapsed: boolean;
  active: boolean;
  onNavigate?: () => void;
}) {
  const label = route.navLabel ?? route.title;

  if (route.visibility === "planned") {
    const content = (
      <div
        aria-disabled="true"
        className={cn(ITEM_CLASS, "text-muted-foreground/60 cursor-default justify-between", collapsed && "justify-center")}
      >
        <span className="flex items-center gap-2">
          {Icon && <Icon className="size-5" aria-hidden="true" />}
          {!collapsed && label}
        </span>
        {!collapsed && (
          <Badge variant="outline" className="text-[10px]">
            Planned
          </Badge>
        )}
      </div>
    );
    return collapsed ? (
      <Tooltip label={`${label} (planned)`} side="right">
        {content}
      </Tooltip>
    ) : (
      content
    );
  }

  const link = (
    <Link
      href={route.path}
      aria-current={active ? "page" : undefined}
      onClick={onNavigate}
      className={cn(
        ITEM_CLASS,
        collapsed && "justify-center",
        active
          ? "bg-muted text-foreground border-primary border-l-2"
          : "text-muted-foreground hover:bg-muted hover:text-foreground border-l-2 border-transparent",
      )}
    >
      {Icon && <Icon className="size-5" aria-hidden="true" />}
      {!collapsed && label}
    </Link>
  );

  return collapsed ? (
    <Tooltip label={label} side="right">
      {link}
    </Tooltip>
  ) : (
    link
  );
}
