import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResourceBreadcrumbs } from "@/components/resource/resource-breadcrumbs";

describe("ResourceBreadcrumbs", () => {
  it("renders nothing for an empty trail", () => {
    const { container } = render(<ResourceBreadcrumbs trail={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("links every ancestor entry and marks the final entry as the current page, unlinked", () => {
    render(
      <ResourceBreadcrumbs
        trail={[
          { label: "Infrastructure", href: "/infrastructure" },
          { label: "Assets", href: "/infrastructure/assets" },
          { label: "edge-01" },
        ]}
      />,
    );

    expect(screen.getByRole("link", { name: "Infrastructure" })).toHaveAttribute("href", "/infrastructure");
    expect(screen.getByRole("link", { name: "Assets" })).toHaveAttribute("href", "/infrastructure/assets");
    expect(screen.getByText("edge-01")).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("link", { name: "edge-01" })).not.toBeInTheDocument();
  });
});
