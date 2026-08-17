import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Breadcrumbs } from "@/components/navigation/breadcrumbs";

const mockPathname = vi.hoisted(() => ({ current: "/" }));
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname.current,
}));

describe("Breadcrumbs", () => {
  it("renders the current route's breadcrumb with aria-current=page for a registered path", () => {
    mockPathname.current = "/";
    render(<Breadcrumbs />);

    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toHaveAttribute("aria-current", "page");
  });

  it("renders nothing for an unregistered path", () => {
    mockPathname.current = "/this-path-does-not-exist";
    const { container } = render(<Breadcrumbs />);

    expect(container).toBeEmptyDOMElement();
  });
});
