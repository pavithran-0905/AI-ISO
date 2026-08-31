import type { SearchResult } from "@/features/search/types";

/**
 * §12: no resource type's real API provides a relevance score — this
 * is this feature's own transparent, documented client ranking, never
 * presented as backend-provided semantic relevance. Tiers, in order:
 * exact title match, exact id match, title starts with the query,
 * title contains the query. `Array.prototype.sort` is stable, so
 * within a tier, results keep whatever order their source query
 * already returned them in (each source's own real, established
 * ordering — e.g. alerts/reports newest-first) as the recency
 * tiebreaker, rather than this module re-deriving one.
 */
function tier(result: SearchResult, query: string): number {
  const title = result.title.toLowerCase();
  if (title === query) return 0;
  if (result.id.toLowerCase() === query) return 1;
  if (title.startsWith(query)) return 2;
  if (title.includes(query)) return 3;
  return 4;
}

export function rankResults(results: SearchResult[], query: string): SearchResult[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return results;
  return [...results].sort((a, b) => tier(a, normalized) - tier(b, normalized));
}
