import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DistributionBar } from "@/features/dashboard/components/distribution-bar";

describe("DistributionBar", () => {
  it("renders nothing when every segment is zero — never a fabricated empty track", () => {
    const { container } = render(
      <DistributionBar segments={[{ key: "a", label: "A", value: 0, tone: "success" }]} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows an accessible text-equivalent legend alongside the visual bar (§40)", () => {
    render(
      <DistributionBar
        segments={[
          { key: "healthy", label: "Healthy", value: 7, tone: "success" },
          { key: "critical", label: "Critical", value: 1, tone: "danger" },
          { key: "warning", label: "Warning", value: 0, tone: "warning" },
        ]}
      />,
    );

    // The visual bar itself carries one summarizing aria-label...
    expect(screen.getByRole("img", { name: /Healthy 7, Critical 1, out of 8 total/ })).toBeInTheDocument();
    // ...and a plain-text legend repeats the same counts, never color alone.
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    // A zero-value segment is omitted from the legend entirely.
    expect(screen.queryByText("Warning")).not.toBeInTheDocument();
  });
});
