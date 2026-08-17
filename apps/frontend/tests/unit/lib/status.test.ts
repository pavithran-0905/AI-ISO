import { describe, expect, it } from "vitest";

import { resolveStatus, STATUS_STATES, STATUS_TAXONOMY, STATUS_TONES } from "@/lib/status";

describe("STATUS_TAXONOMY", () => {
  it("defines an entry for every named state", () => {
    for (const state of STATUS_STATES) {
      expect(STATUS_TAXONOMY[state]).toBeDefined();
    }
  });

  it("only ever resolves to a defined tone", () => {
    for (const state of STATUS_STATES) {
      expect(STATUS_TONES).toContain(STATUS_TAXONOMY[state].tone);
    }
  });

  it("gives healthy and completed the same (success) tone deliberately", () => {
    expect(STATUS_TAXONOMY.healthy.tone).toBe("success");
    expect(STATUS_TAXONOMY.completed.tone).toBe("success");
  });

  it("gives every state a non-empty label", () => {
    for (const state of STATUS_STATES) {
      expect(STATUS_TAXONOMY[state].label.length).toBeGreaterThan(0);
    }
  });
});

describe("resolveStatus", () => {
  it("returns the taxonomy entry for a given state", () => {
    expect(resolveStatus("critical")).toEqual(STATUS_TAXONOMY.critical);
  });
});
