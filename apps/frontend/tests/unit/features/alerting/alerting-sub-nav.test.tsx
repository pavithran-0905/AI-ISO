import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertingSubNav } from "@/features/alerting/components/alerting-sub-nav";

const mockPathname = vi.hoisted(() => ({ current: "/alerting" }));
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname.current,
}));

describe("AlertingSubNav", () => {
  it("marks the current section as the current page", () => {
    mockPathname.current = "/alerting/alerts";
    render(<AlertingSubNav />);

    expect(screen.getByRole("link", { name: "Alerts" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
  });

  it("links to every real alerting section", () => {
    mockPathname.current = "/alerting";
    render(<AlertingSubNav />);

    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/alerting");
    expect(screen.getByRole("link", { name: "Alerts" })).toHaveAttribute("href", "/alerting/alerts");
  });
});
