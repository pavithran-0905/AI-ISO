import { describe, expect, it } from "vitest";

import { formatRelativeTime } from "@/lib/relative-time";

const NOW = new Date("2026-01-01T12:00:00Z");

describe("formatRelativeTime", () => {
  it("returns 'just now' for a timestamp under a minute old", () => {
    expect(formatRelativeTime("2026-01-01T11:59:30Z", NOW)).toBe("just now");
  });

  it("formats minutes ago", () => {
    expect(formatRelativeTime("2026-01-01T11:55:00Z", NOW)).toBe("5 minutes ago");
  });

  it("formats hours ago", () => {
    expect(formatRelativeTime("2026-01-01T09:00:00Z", NOW)).toBe("3 hours ago");
  });

  it("formats a future timestamp", () => {
    expect(formatRelativeTime("2026-01-01T12:10:00Z", NOW)).toBe("in 10 minutes");
  });
});
