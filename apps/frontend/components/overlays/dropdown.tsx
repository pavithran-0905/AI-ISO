"use client";

import type { LucideIcon } from "lucide-react";
import { useRef } from "react";

import { useDismissableLayer } from "@/components/overlays/use-dismissable-layer";
import { cn } from "@/utils/cn";

export interface DropdownItem {
  label: string;
  onSelect: () => void;
  destructive?: boolean;
  disabled?: boolean;
  icon?: LucideIcon;
}

export interface DropdownProps {
  open: boolean;
  onClose: () => void;
  trigger: React.ReactNode;
  items: DropdownItem[];
  align?: "start" | "end";
  /** Non-interactive content above the items (e.g. `UserMenu`'s own
   * identity block) — excluded from the `role="menuitem"` roving-focus
   * set on purpose, since it isn't a menu item. */
  header?: React.ReactNode;
}

/**
 * An action menu (§12) — `role="menu"`/`"menuitem"` with arrow-key
 * navigation between items, Home/End to jump, Escape/outside-click to
 * dismiss (via `useDismissableLayer`, shared with `Popover`).
 * Destructive items (`destructive: true`) get the `danger` tone per
 * §11's icon rules.
 */
export function Dropdown({ open, onClose, trigger, items, align = "start", header }: DropdownProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  useDismissableLayer(open, containerRef, onClose);

  function focusItem(index: number) {
    const menu = containerRef.current?.querySelector('[role="menu"]');
    const menuItems = menu?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([aria-disabled="true"])');
    if (!menuItems || menuItems.length === 0) return;
    const clamped = ((index % menuItems.length) + menuItems.length) % menuItems.length;
    menuItems[clamped]?.focus();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const menu = containerRef.current?.querySelector('[role="menu"]');
    const menuItems = Array.from(menu?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([aria-disabled="true"])') ?? []);
    const currentIndex = menuItems.indexOf(document.activeElement as HTMLElement);

    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusItem(currentIndex + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusItem(currentIndex - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusItem(0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusItem(menuItems.length - 1);
    }
  }

  return (
    <div ref={containerRef} className="relative inline-block" onKeyDown={handleKeyDown}>
      {trigger}
      {open && (
        <div
          role="menu"
          className={cn(
            "bg-surface-elevated border-border absolute z-dropdown mt-1.5 min-w-40 rounded-lg border p-1 shadow-elevation-3",
            "motion-safe:animate-overlay-in",
            align === "start" ? "left-0" : "right-0",
          )}
        >
          {header}
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                type="button"
                role="menuitem"
                aria-disabled={item.disabled || undefined}
                disabled={item.disabled}
                onClick={() => {
                  item.onSelect();
                  onClose();
                }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                  "hover:bg-muted focus-visible:bg-muted focus-visible:outline-none",
                  "disabled:pointer-events-none disabled:opacity-50",
                  item.destructive ? "text-danger" : "text-foreground",
                )}
              >
                {Icon && <Icon className="size-4" aria-hidden="true" />}
                {item.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
