"use client";

import { Search, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { useGlobalSearch } from "@/features/search/hooks/use-global-search";
import { SEARCH_RESULT_TYPE_LABELS, type SearchResult } from "@/features/search/types";
import { usePermissions } from "@/permissions/hooks";
import { ROUTE_REGISTRY, type RouteMeta } from "@/lib/route-registry";
import { useCommandPaletteStore } from "@/state/command-palette-store";
import { useRecentSearchesStore } from "@/state/recent-searches-store";
import { cn } from "@/utils/cn";

/** Navigation commands (docs/frontend Prompt 003 §15: "do not invent
 * backend actions") — every `"implemented"` route, independent of
 * `showInNav`, filtered by role the same way `PrimaryNavigation`
 * already does (§23: permission-aware results — a route hidden from
 * the sidebar for this session's role must not appear here either). */
const ALL_NAVIGATION_COMMANDS = ROUTE_REGISTRY.filter((route) => route.visibility === "implemented");

function matchesRoute(route: RouteMeta, query: string): boolean {
  const haystack = `${route.title} ${route.description}`.toLowerCase();
  return haystack.includes(query.toLowerCase());
}

type FlatItem = { kind: "page"; route: RouteMeta } | { kind: "result"; result: SearchResult };

/**
 * The global command palette (docs/frontend Prompt 003 §15, extended
 * in Prompt 017 with real cross-module resource search) — a native
 * `<dialog>` (real focus trap/Escape-to-close), search input, results
 * as a real `role="listbox"`/`"option"` list grouped by type. Opens
 * via `Ctrl`/`Cmd+K` or `useCommandPaletteStore.show()`.
 *
 * There is no global search backend API (confirmed absent — see
 * `docs/frontend/developer-guide/global-search.md`): resource results
 * compose existing feature API modules through `useGlobalSearch`,
 * never a new HTTP call from this component.
 */
export function CommandPalette() {
  const open = useCommandPaletteStore((state) => state.open);
  const show = useCommandPaletteStore((state) => state.show);
  const hide = useCommandPaletteStore((state) => state.hide);
  const { role } = usePermissions();
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const recentSearches = useRecentSearchesStore((state) => state.terms);
  const addRecentSearch = useRecentSearchesStore((state) => state.addSearch);
  const clearRecentSearches = useRecentSearchesStore((state) => state.clear);

  const navigationCommands = useMemo(
    () => ALL_NAVIGATION_COMMANDS.filter((route) => route.roles === null || (role !== null && route.roles.includes(role))),
    [role],
  );

  const trimmedQuery = query.trim();
  const matchingPages = useMemo(
    () => (trimmedQuery === "" ? navigationCommands : navigationCommands.filter((route) => matchesRoute(route, trimmedQuery))),
    [navigationCommands, trimmedQuery],
  );

  const { groups, isSearching } = useGlobalSearch(trimmedQuery, open);

  // Record a settled, real search term once results have actually
  // loaded — not on every keystroke, and never sent anywhere but this
  // session's own local storage (§21).
  useEffect(() => {
    if (trimmedQuery.length >= 2 && !isSearching) addRecentSearch(trimmedQuery);
  }, [trimmedQuery, isSearching, addRecentSearch]);

  const flatItems: FlatItem[] = useMemo(() => {
    const pageItems: FlatItem[] = matchingPages.map((route) => ({ kind: "page", route }));
    const resultItems: FlatItem[] = groups.flatMap((group) => group.results.map((result) => ({ kind: "result", result }) as const));
    return [...pageItems, ...resultItems];
  }, [matchingPages, groups]);

  // Reset the highlighted result whenever the query changes — adjusted
  // during render (React's documented pattern) rather than a
  // `useEffect`, avoiding an extra cascading render.
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

  function navigateToPath(path: string) {
    hide();
    router.push(path);
  }

  function openItem(item: FlatItem) {
    navigateToPath(item.kind === "page" ? item.route.path : item.result.href);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, Math.max(flatItems.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const selected = flatItems[activeIndex];
      if (selected) openItem(selected);
    }
  }

  const activeId =
    flatItems[activeIndex] &&
    (flatItems[activeIndex].kind === "page" ? `command-palette-page-${flatItems[activeIndex].route.id}` : `command-palette-result-${flatItems[activeIndex].result.id}`);

  const showRecent = trimmedQuery === "" && recentSearches.length > 0;
  const hasAnyResourceGroups = groups.length > 0;
  const noResults = trimmedQuery !== "" && matchingPages.length === 0 && !hasAnyResourceGroups && !isSearching;

  return (
    <dialog
      ref={dialogRef}
      onClose={hide}
      onCancel={hide}
      aria-label="Command palette"
      className={cn(
        "bg-surface-elevated text-foreground fixed inset-0 m-0 hidden h-full max-h-none w-full max-w-none flex-col rounded-none border-0 p-0 open:flex",
        "sm:relative sm:inset-auto sm:m-auto sm:h-auto sm:max-h-[80vh] sm:w-full sm:max-w-lg sm:rounded-lg sm:border sm:border-border",
        "shadow-elevation-3 backdrop:bg-foreground/40 motion-safe:open:animate-dialog-in",
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
          aria-expanded={flatItems.length > 0}
          aria-controls="command-palette-listbox"
          aria-activedescendant={activeId || undefined}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search AI-IOS…"
          className="h-11 w-full bg-transparent text-sm outline-none"
        />
        <button type="button" onClick={hide} className="text-muted-foreground hover:text-foreground shrink-0 sm:hidden" aria-label="Close command palette">
          <X className="size-5" aria-hidden="true" />
        </button>
      </div>

      {/* A polite live region, not tied to visual highlighting alone
          (§37) — announces state changes a sighted user sees as the
          spinner/result count, without narrating every keystroke. */}
      <p className="sr-only" role="status" aria-live="polite">
        {isSearching ? "Searching…" : trimmedQuery !== "" ? `${flatItems.length} result${flatItems.length === 1 ? "" : "s"}` : ""}
      </p>

      <div id="command-palette-listbox" role="listbox" aria-label="Results" className="flex-1 overflow-y-auto p-1 sm:max-h-80">
        {showRecent && (
          <div role="group" aria-label="Recent searches" className="border-border mb-1 border-b pb-1">
            <div className="text-muted-foreground flex items-center justify-between px-3 py-1 text-xs font-medium">
              <span>Recent searches</span>
              <button type="button" onClick={clearRecentSearches} className="hover:text-foreground underline-offset-2 hover:underline">
                Clear
              </button>
            </div>
            {recentSearches.map((term) => (
              <button
                key={term}
                type="button"
                onClick={() => setQuery(term)}
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm"
              >
                <Search className="text-muted-foreground size-3.5 shrink-0" aria-hidden="true" />
                {term}
              </button>
            ))}
          </div>
        )}

        {matchingPages.length > 0 && (
          <div role="group" aria-label="Pages" className="mb-1">
            {trimmedQuery !== "" && <p className="text-muted-foreground px-3 py-1 text-xs font-medium">Pages</p>}
            {matchingPages.map((route) => {
              const index = flatItems.findIndex((item) => item.kind === "page" && item.route.id === route.id);
              return (
                <button
                  key={route.id}
                  id={`command-palette-page-${route.id}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  type="button"
                  onClick={() => navigateToPath(route.path)}
                  onMouseEnter={() => setActiveIndex(index)}
                  className={cn(
                    "flex w-full flex-col items-start gap-0.5 rounded-md px-3 py-2 text-left text-sm",
                    index === activeIndex ? "bg-muted text-foreground" : "text-foreground",
                  )}
                >
                  <span className="font-medium">{route.title}</span>
                  <span className="text-muted-foreground text-xs">{route.description}</span>
                </button>
              );
            })}
          </div>
        )}

        {groups.map((group) => (
          <div key={group.type} role="group" aria-label={SEARCH_RESULT_TYPE_LABELS[group.type]} className="mb-1">
            <p className="text-muted-foreground flex items-center gap-1.5 px-3 py-1 text-xs font-medium">
              {group.label}
              {group.isError && <span className="text-warning">— temporarily unavailable</span>}
            </p>
            {group.results.map((result) => {
              const index = flatItems.findIndex((item) => item.kind === "result" && item.result.id === result.id && item.result.resultType === result.resultType);
              return (
                <button
                  key={`${result.resultType}-${result.id}`}
                  id={`command-palette-result-${result.id}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  type="button"
                  onClick={() => navigateToPath(result.href)}
                  onMouseEnter={() => setActiveIndex(index)}
                  className={cn(
                    "flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm",
                    index === activeIndex ? "bg-muted text-foreground" : "text-foreground",
                  )}
                >
                  <span className="flex flex-col items-start gap-0.5">
                    <span className="font-medium">{result.title}</span>
                    {result.description && <span className="text-muted-foreground text-xs">{result.description}</span>}
                  </span>
                  {result.status && <StatusBadge tone="neutral" label={result.status} className="shrink-0" />}
                </button>
              );
            })}
          </div>
        ))}

        {noResults && (
          <EmptyState
            title={`No results for "${trimmedQuery}"`}
            description="Try a different name, identifier, or resource type."
            className="p-6"
          />
        )}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-border px-3 py-2">
        <p className="text-muted-foreground hidden text-xs sm:block">
          <kbd className="rounded border px-1">↑↓</kbd> Navigate <kbd className="ml-2 rounded border px-1">Enter</kbd> Open{" "}
          <kbd className="ml-2 rounded border px-1">Esc</kbd> Close
        </p>
        <div className="flex items-center gap-2">
          {trimmedQuery !== "" && (
            <Link
              href={`/intelligence/assistant?draft=${encodeURIComponent(trimmedQuery)}`}
              onClick={hide}
              className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-xs"
            >
              <Sparkles className="size-3.5" aria-hidden="true" />
              Ask AI
            </Link>
          )}
          {trimmedQuery !== "" && (
            <Link href={`/search?q=${encodeURIComponent(trimmedQuery)}`} onClick={hide} className="text-primary text-xs hover:underline">
              View all results
            </Link>
          )}
        </div>
      </div>
    </dialog>
  );
}
