"use client";

import { useId, useRef } from "react";

import { cn } from "@/utils/cn";

export interface TabItem {
  id: string;
  label: string;
}

export interface TabsProps {
  items: TabItem[];
  activeId: string;
  onChange: (id: string) => void;
  children: React.ReactNode;
  className?: string;
}

/**
 * The standard WAI-ARIA Tabs pattern (§12): `role="tablist"`/`"tab"`/
 * `"tabpanel"`, roving `tabindex` (only the active tab is in the tab
 * order; arrow keys move both focus and selection between the rest),
 * Home/End to jump. `children` should be the active panel's content
 * only — `Tabs` doesn't render inactive panels, so a feature never pays
 * for hidden panel work.
 */
export function Tabs({ items, activeId, onChange, children, className }: TabsProps) {
  const baseId = useId();
  const listRef = useRef<HTMLDivElement>(null);

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const currentIndex = items.findIndex((item) => item.id === activeId);
    let nextIndex: number | null = null;

    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % items.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + items.length) % items.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = items.length - 1;

    if (nextIndex !== null) {
      event.preventDefault();
      const nextItem = items[nextIndex];
      onChange(nextItem.id);
      listRef.current?.querySelector<HTMLElement>(`#${CSS.escape(`${baseId}-tab-${nextItem.id}`)}`)?.focus();
    }
  }

  return (
    <div className={className}>
      <div ref={listRef} role="tablist" onKeyDown={handleKeyDown} className="border-border flex gap-1 border-b">
        {items.map((item) => {
          const selected = item.id === activeId;
          return (
            <button
              key={item.id}
              id={`${baseId}-tab-${item.id}`}
              role="tab"
              type="button"
              aria-selected={selected}
              aria-controls={`${baseId}-panel-${item.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(item.id)}
              className={cn(
                "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                "focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
                selected
                  ? "border-primary text-foreground"
                  : "text-muted-foreground hover:text-foreground border-transparent",
              )}
            >
              {item.label}
            </button>
          );
        })}
      </div>
      <div id={`${baseId}-panel-${activeId}`} role="tabpanel" aria-labelledby={`${baseId}-tab-${activeId}`} className="pt-4">
        {children}
      </div>
    </div>
  );
}
