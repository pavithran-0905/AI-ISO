import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageHeader } from "@/components/navigation/page-header";

describe("PageHeader", () => {
  it("renders eyebrow, title, status, and description", () => {
    render(
      <PageHeader
        eyebrow="Operations"
        title="Monitoring"
        description="Track system health in real time."
        status={<span>Healthy</span>}
      />,
    );

    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Monitoring" })).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Track system health in real time.")).toBeInTheDocument();
  });

  it("omits the actions row entirely when no action is provided", () => {
    render(<PageHeader title="Monitoring" />);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("renders secondary actions before the primary action, with overflow actions last", () => {
    render(
      <PageHeader
        title="Monitoring"
        secondaryActions={<button>Export</button>}
        primaryAction={<button>Create alert</button>}
        overflowActions={<button>More</button>}
      />,
    );

    const buttons = screen.getAllByRole("button").map((button) => button.textContent);
    expect(buttons).toEqual(["Export", "Create alert", "More"]);
  });
});
