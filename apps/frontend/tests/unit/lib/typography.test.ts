import { describe, expect, it } from "vitest";

import { typography } from "@/lib/typography";

describe("typography", () => {
  it("defines a non-empty className for every token", () => {
    for (const [token, className] of Object.entries(typography)) {
      expect(className.length, `${token} should have a non-empty className`).toBeGreaterThan(0);
    }
  });

  it("gives metric tokens tabular figures so aligned columns don't jitter", () => {
    expect(typography.metric).toContain("tabular-nums");
  });
});
