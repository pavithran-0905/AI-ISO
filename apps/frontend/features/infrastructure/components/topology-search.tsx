"use client";

import { Search } from "lucide-react";
import { useEffect, useState } from "react";

import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { useAssetSearch } from "@/features/infrastructure/hooks/use-assets";

/**
 * §14: real server-side search (`GET /inventory/search`), never a
 * client-side filter over whatever happens to already be loaded in
 * the graph. Selecting a result re-focuses the topology on that asset
 * (a real, new `GET /inventory/topology` request), never a
 * client-side re-render pretending to be a new query.
 */
export function TopologySearch({ organizationId, onFocusAsset }: { organizationId: string; onFocusAsset: (assetId: string) => void }) {
  const [inputValue, setInputValue] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(inputValue.trim()), 300);
    return () => clearTimeout(timer);
  }, [inputValue]);

  const searchQuery = useAssetSearch(
    debouncedQuery.length >= 2 ? { organizationId, query: debouncedQuery, page: 1, pageSize: 8 } : null,
  );
  const results = searchQuery.data?.items ?? [];

  function handleSelect(assetId: string) {
    onFocusAsset(assetId);
    setInputValue("");
    setDebouncedQuery("");
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="topology-search">Search assets</Label>
      <div className="relative">
        <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
        <Input
          id="topology-search"
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          placeholder="Search by name, hostname, IP, serial…"
          className="pl-9"
        />
      </div>

      {debouncedQuery.length >= 2 && (
        <div className="border-border bg-card mt-1 max-h-64 overflow-y-auto rounded-md border shadow-sm">
          {searchQuery.isLoading && <p className="text-muted-foreground p-3 text-xs">Searching…</p>}
          {searchQuery.isError && <p className="text-danger p-3 text-xs">Search failed. Try again.</p>}
          {searchQuery.data && results.length === 0 && (
            <p className="text-muted-foreground p-3 text-xs">No assets match &ldquo;{debouncedQuery}&rdquo;.</p>
          )}
          {results.length > 0 && (
            <ul>
              {results.map((asset) => (
                <li key={asset.id}>
                  <button
                    type="button"
                    onClick={() => handleSelect(asset.id)}
                    className="hover:bg-muted focus-visible:bg-muted focus-visible:ring-ring flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-xs focus-visible:ring-2 focus-visible:outline-none"
                  >
                    <span className="font-medium">{asset.displayName ?? asset.name}</span>
                    <span className="text-muted-foreground">{asset.assetType}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="sr-only" aria-live="polite">
            {results.length} result{results.length === 1 ? "" : "s"} for {debouncedQuery}.
          </p>
        </div>
      )}
    </div>
  );
}
