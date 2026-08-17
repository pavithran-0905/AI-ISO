"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ROUTE_REGISTRY, type RouteMeta } from "@/lib/route-registry";
import { useCommandPaletteStore } from "@/state/command-palette-store";
import { cn } from "@/utils/cn";

/** Navigation commands only (docs/frontend Prompt 003 §15: "do not
 * invent backend actions") — every `"implemented"` route, independent
 * of `showInNav` (a route can be navigable without being in the
 * sidebar, e.g. `/design-system`). */
const NAVIGATION_COMMANDS = ROUTE_REGISTRY.filter((route) => route.visibility === "implemented");

function matches(route: RouteMeta, query: string): boolean {
  const haystack = `${route.title} ${route.description}`.toLowerCase();
  return haystack.includes(query.toLowerCase());
}

/**
 * The global command palette (docs/frontend Prompt 003 §15) — a native
 * `<dialog>` (real focus trap/Escape-to-close, same primitive as
 * `Dialog`/`Drawer`) deliberately without their header/footer chrome:
 * a search input immediately inside, results as a real
 * `role="listbox"`/`"option"` list. Opens via `Ctrl`/`Cmd+K` (global
 * listener, mounted once here) or `useCommandPaletteStore`'s `show()`.
 */
export function CommandPalette() {
  const open = useCommandPaletteStore((state) => state.open);
  const show = useCommandPaletteStore((state) => state.show);
  const hide = useCommandPaletteStore((state) => state.hide);
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const results = useMemo(
    () => (query.trim() === "" ? NAVIGATION_COMMANDS : NAVIGATION_COMMANDS.filter((route) => matches(route, query))),
    [query],
  );

  // Reset the highlighted result whenever the query changes. Adjusted
  // during render (React's documented pattern for resetting state in
  // response to a prop/state change) rather than in a `useEffect`, which
  // would cause an extra cascading render.
  const [queryForActiveIndex, setQueryForActiveIndex] = useState(query);
  if (query !== queryForActiveIndex) {
    setQueryForActiveIndex(query);
    setActiveIndex(0);
  }

  useEffect(() => {
    function handleGlobalKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        show();
      }
    }
    document.addEventListener("keydown", handleGlobalKeyDown);
    return () => document.removeEventListener("keydown", handleGlobalKeyDown);
  }, [show]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      setQuery("");
      setActiveIndex(0);
      inputRef.current?.focus();
    }
    if (!open && dialog.open) dialog.close();
  }, [open]);

  function navigateTo(route: RouteMeta) {
    hide();
    router.push(route.path);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const selected = results[activeIndex];
      if (selected) navigateTo(selected);
    }
  }

  return (
    <dialog
      ref={dialogRef}
      onClose={hide}
      onCancel={hide}
      aria-label="Command palette"
      className={cn(
        "bg-surface-elevated text-foreground w-full max-w-lg rounded-lg border border-border p-0 shadow-elevation-3",
        "backdrop:bg-foreground/40",
        "motion-safe:open:animate-dialog-in",
      )}
      onClick={(event) => {
        if (event.target === dialogRef.current) hide();
      }}
    >
      <div className="flex items-center gap-2 border-b border-border px-3">
        <Search className="text-muted-foreground size-4 shrink-0" aria-hidden="true" />
        <input
          ref={inputRef}
          role="combobox"
          aria-expanded={results.length > 0}
          aria-controls="command-palette-listbox"
          aria-activedescendant={results[activeIndex] ? `command-palette-option-${results[activeIndex].id}` : undefined}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search pages and commands…"
          className="h-11 w-full bg-transparent text-sm outline-none"
        />
      </div>
      <div id="command-palette-listbox" role="listbox" aria-label="Results" className="max-h-80 overflow-y-auto p-1">
        {results.length === 0 ? (
          <EmptyState title="No matching pages" className="p-6" />
        ) : (
          results.map((route, index) => (
            <button
              key={route.id}
              id={`command-palette-option-${route.id}`}
              role="option"
              aria-selected={index === activeIndex}
              type="button"
              onClick={() => navigateTo(route)}
              onMouseEnter={() => setActiveIndex(index)}
              className={cn(
                "flex w-full flex-col items-start gap-0.5 rounded-md px-3 py-2 text-left text-sm",
                index === activeIndex ? "bg-muted text-foreground" : "text-foreground",
              )}
            >
              <span className="font-medium">{route.title}</span>
              <span className="text-muted-foreground text-xs">{route.description}</span>
            </button>
          ))
        )}
      </div>
    </dialog>
  );
}
