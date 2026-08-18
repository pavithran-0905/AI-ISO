import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MonitoringSubNav } from "@/features/monitoring/components/monitoring-sub-nav";

const mockPathname = vi.hoisted(() => ({ current: "/monitoring" }));
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname.current,
}));

describe("MonitoringSubNav", () => {
  it("marks the current section as the current page", () => {
    mockPathname.current = "/monitoring/assets";
    render(<MonitoringSubNav />);

    expect(screen.getByRole("link", { name: "Assets" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
  });

  it("links to every real monitoring section", () => {
    mockPathname.current = "/monitoring";
    render(<MonitoringSubNav />);

    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/monitoring");
    expect(screen.getByRole("link", { name: "Assets" })).toHaveAttribute("href", "/monitoring/assets");
    expect(screen.getByRole("link", { name: "Services" })).toHaveAttribute("href", "/monitoring/services");
    expect(screen.getByRole("link", { name: "Events" })).toHaveAttribute("href", "/monitoring/events");
  });
});
