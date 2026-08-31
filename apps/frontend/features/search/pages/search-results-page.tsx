"use client";

import { Search, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { StatusBadge } from "@/components/feedback/status-badge";
import { PageHeader } from "@/components/navigation/page-header";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { useGlobalSearch } from "@/features/search/hooks/use-global-search";
import { SEARCH_RESULT_TYPES, SEARCH_RESULT_TYPE_LABELS, type SearchResultType } from "@/features/search/types";
import { typography } from "@/lib/typography";
import { cn } from "@/utils/cn";

const RESULTS_PER_GROUP = 20;

/**
 * `/search` (§15) — a dedicated, URL-addressable results page
 * (`?q=`), reusing the exact same `useGlobalSearch` composition the
 * command palette uses, just with a larger per-group limit. Never a
 * duplicate of the application's own navigation (§15's own
 * instruction) — a scope selector narrows to one resource type, it
 * doesn't reproduce the sidebar.
 */
export function SearchResultsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlQuery = searchParams.get("q") ?? "";
  const [inputValue, setInputValue] = useState(urlQuery);
  const scope = (searchParams.get("scope") as SearchResultType | "all" | null) ?? "all";

  const { groups, isSearching, queryLongEnough, orgReady } = useGlobalSearch(urlQuery, true, RESULTS_PER_GROUP);
  const visibleGroups = useMemo(() => (scope === "all" ? groups : groups.filter((group) => group.type === scope)), [groups, scope]);
  const totalResults = visibleGroups.reduce((sum, group) => sum + group.results.length, 0);

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    const params = new URLSearchParams(searchParams.toString());
    if (inputValue.trim()) params.set("q", inputValue.trim());
    else params.delete("q");
    router.push(`/search?${params.toString()}`);
  }

  function setScope(nextScope: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (nextScope === "all") params.delete("scope");
    else params.set("scope", nextScope);
    router.push(`/search?${params.toString()}`);
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Search" description="Find and navigate to resources across AI-IOS." />

      <form onSubmit={submitSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
          <Input
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            placeholder="Search AI-IOS…"
            className="pl-9"
            aria-label="Search query"
          />
        </div>
      </form>

      {urlQuery.trim() !== "" && (
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Search scope">
          <button
            type="button"
            onClick={() => setScope("all")}
            className={cn("rounded-full border px-3 py-1 text-xs font-medium", scope === "all" ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground")}
          >
            All
          </button>
          {SEARCH_RESULT_TYPES.map((type) => {
            const group = groups.find((candidate) => candidate.type === type);
            if (!group) return null;
            return (
              <button
                key={type}
                type="button"
                onClick={() => setScope(type)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium",
                  scope === type ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground",
                )}
              >
                {SEARCH_RESULT_TYPE_LABELS[type]} ({group.results.length})
              </button>
            );
          })}
        </div>
      )}

      {!queryLongEnough && urlQuery.trim() !== "" && (
        <EmptyState title="Type at least 2 characters" description="Search needs a slightly longer query to run." />
      )}

      {urlQuery.trim() === "" && <EmptyState icon={Search} title="Search AI-IOS" description="Type a name, identifier, or keyword above." />}

      {!orgReady && urlQuery.trim() !== "" && (
        <EmptyState title="No organization selected" description="Select an organization to search its resources." />
      )}

      {orgReady && queryLongEnough && (
        <div className="flex flex-col gap-8">
          {totalResults === 0 && !isSearching && (
            <EmptyState title={`No results for "${urlQuery}"`} description="Try a different name, identifier, or resource type." />
          )}

          {visibleGroups.map((group) => (
            <section key={group.type}>
              <div className="mb-3 flex items-center gap-2">
                <h2 className={typography.cardTitle}>{group.label}</h2>
                {group.isError && <StatusBadge tone="warning" label="Temporarily unavailable" />}
                {group.isLoading && <span className="text-muted-foreground text-xs">Loading…</span>}
              </div>
              {group.results.length === 0 ? (
                !group.isLoading && !group.isError && <p className="text-muted-foreground text-sm">No matches.</p>
              ) : (
                <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {group.results.map((result) => (
                    <li key={`${result.resultType}-${result.id}`}>
                      <Link href={result.href} className="border-border hover:border-muted-foreground/50 flex flex-col gap-1 rounded-lg border p-3 transition-colors">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-medium">{result.title}</span>
                          {result.status && <StatusBadge tone="neutral" label={result.status} />}
                        </div>
                        {result.description && <span className="text-muted-foreground text-xs">{result.description}</span>}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}

          <Link href={`/intelligence/assistant?draft=${encodeURIComponent(urlQuery)}`} className={cn(buttonVariants("outline", "w-fit gap-1.5"))}>
            <Sparkles className="size-4" aria-hidden="true" />
            Ask AI about &quot;{urlQuery}&quot;
          </Link>
        </div>
      )}
    </div>
  );
}
