import { afterEach, describe, expect, it } from "vitest";

import { useTableDensityStore } from "@/state/table-density-store";

describe("useTableDensityStore", () => {
  afterEach(() => {
    useTableDensityStore.setState({ density: "comfortable" });
  });

  it("starts comfortable", () => {
    expect(useTableDensityStore.getState().density).toBe("comfortable");
  });

  it("setDensity() switches and persists the preference", () => {
    useTableDensityStore.getState().setDensity("compact");
    expect(useTableDensityStore.getState().density).toBe("compact");
  });
});
