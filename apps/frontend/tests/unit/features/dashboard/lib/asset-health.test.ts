import { describe, expect, it } from "vitest";

import { buildHealthSegments, computePlatformHealthTier } from "@/features/dashboard/lib/asset-health";

describe("buildHealthSegments", () => {
  it("returns one segment per real AssetHealthValue, in taxonomy order", () => {
    const segments = buildHealthSegments({ healthy: 7, warning: 2, critical: 1 });
    expect(segments.map((s) => s.key)).toEqual(["healthy", "warning", "critical", "unknown", "offline", "unreachable"]);
    expect(segments.find((s) => s.key === "healthy")).toMatchObject({ value: 7, tone: "success" });
    expect(segments.find((s) => s.key === "critical")).toMatchObject({ value: 1, tone: "danger" });
    expect(segments.find((s) => s.key === "unknown")).toMatchObject({ value: 0, tone: "unknown" });
  });
});

describe("computePlatformHealthTier", () => {
  it("returns null when there is no distribution at all", () => {
    expect(computePlatformHealthTier(undefined)).toBeNull();
  });

  it("returns null when every count is zero — never a fabricated Healthy badge", () => {
    expect(computePlatformHealthTier({ healthy: 0, warning: 0 })).toBeNull();
  });

  it("returns critical when any critical or unreachable asset exists", () => {
    expect(computePlatformHealthTier({ healthy: 9, critical: 1 })).toBe("critical");
    expect(computePlatformHealthTier({ healthy: 9, unreachable: 1 })).toBe("critical");
  });

  it("returns warning when no critical tier is present but warning/offline/unknown is", () => {
    expect(computePlatformHealthTier({ healthy: 9, warning: 1 })).toBe("warning");
    expect(computePlatformHealthTier({ healthy: 9, offline: 1 })).toBe("warning");
  });

  it("returns healthy only when every real asset is healthy", () => {
    expect(computePlatformHealthTier({ healthy: 10 })).toBe("healthy");
  });
});
