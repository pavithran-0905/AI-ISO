"use client";

import { Search } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { EmptyState } from "@/components/feedback/empty-state";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Button } from "@/components/ui/button";
import { useKnowledgeSearch } from "@/features/ai-assistant/hooks/use-knowledge";
import { RETRIEVAL_STRATEGIES, type RetrievalStrategyValue } from "@/features/ai-assistant/types";
import { toast } from "@/state/toast-store";

/**
 * A genuine preview of retrieval (§5-adjacent), not a disconnected demo
 * — this calls the exact same `RagPipeline` `/ai/chat` uses internally
 * (see `knowledge-api.ts`'s own module docstring). Search results are
 * inherently query-shaped, not a stable list, so this renders its own
 * transient result set rather than reusing a cached query.
 */
export function KnowledgeSearchPanel({ organizationId }: { organizationId: string }) {
  const [query, setQuery] = useState("");
  const [strategy, setStrategy] = useState<RetrievalStrategyValue>("hybrid");
  const [hasSearched, setHasSearched] = useState(false);
  const search = useKnowledgeSearch();

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    try {
      await search.mutateAsync({ organizationId, query: query.trim(), strategy });
      setHasSearched(true);
    } catch (error) {
      const description = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Search failed", description);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
        <div className="flex min-w-[16rem] flex-1 flex-col gap-1.5">
          <Label htmlFor="knowledge-search-query">Query</Label>
          <Input id="knowledge-search-query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="What would you ask the assistant?" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="knowledge-search-strategy">Strategy</Label>
          <Select id="knowledge-search-strategy" value={strategy} onChange={(event) => setStrategy(event.target.value as RetrievalStrategyValue)} className="w-32">
            {RETRIEVAL_STRATEGIES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </div>
        <Button type="submit" loading={search.isPending} disabled={!query.trim()} className="gap-1.5">
          <Search className="size-4" aria-hidden="true" />
          Search
        </Button>
      </form>

      {hasSearched && search.data && search.data.length === 0 && (
        <EmptyState icon={Search} title="No matches" description="Nothing in the knowledge base scored highly enough for this query." />
      )}

      {search.data && search.data.length > 0 && (
        <ul className="divide-border border-border divide-y rounded-md border">
          {search.data.map((hit) => (
            <li key={hit.chunkId} className="flex flex-col gap-1 p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{hit.documentTitle}</span>
                <span className="text-muted-foreground text-xs">{Math.round(hit.score * 100)}% match</span>
              </div>
              <p className="text-muted-foreground line-clamp-3 text-xs">{hit.content}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
