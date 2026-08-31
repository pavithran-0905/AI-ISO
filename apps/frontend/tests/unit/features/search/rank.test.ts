import { describe, expect, it } from "vitest";

import { rankResults } from "@/features/search/lib/rank";
import type { SearchResult } from "@/features/search/types";

function result(id: string, title: string): SearchResult {
  return { id, resultType: "asset", title, description: null, status: null, href: `/x/${id}` };
}

describe("rankResults", () => {
  it("returns results unchanged for an empty query", () => {
    const results = [result("1", "b"), result("2", "a")];
    expect(rankResults(results, "")).toEqual(results);
  });

  it("ranks an exact title match first, an exact id match second, a prefix third, a substring last", () => {
    const substring = result("x", "the edge-01 server");
    const prefix = result("y", "edge-01-backup");
    const idMatch = result("edge-01", "Some Other Title");
    const exact = result("z", "edge-01");

    const ranked = rankResults([substring, prefix, idMatch, exact], "edge-01");
    expect(ranked.map((r) => r.id)).toEqual(["z", "edge-01", "y", "x"]);
  });

  it("is case-insensitive", () => {
    const ranked = rankResults([result("1", "EDGE-01")], "edge-01");
    expect(ranked[0].id).toBe("1");
  });

  it("preserves each tier's original (source-provided) order as a stable tiebreaker", () => {
    const first = result("1", "edge report alpha");
    const second = result("2", "edge report beta");
    const ranked = rankResults([first, second], "edge");
    expect(ranked.map((r) => r.id)).toEqual(["1", "2"]);
  });
});
