import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusIndicator } from "@/components/data-display/status-indicator";

describe("StatusIndicator", () => {
  it("renders the taxonomy's default label for a named state", () => {
    render(<StatusIndicator state="healthy" />);
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });

  it("renders an icon (not just a dot) from the taxonomy", () => {
    const { container } = render(<StatusIndicator state="running" />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("allows overriding the label while keeping the taxonomy's tone/icon", () => {
    render(<StatusIndicator state="degraded" label="2 of 6 nodes degraded" />);
    expect(screen.getByText("2 of 6 nodes degraded")).toBeInTheDocument();
    expect(screen.queryByText("Degraded")).not.toBeInTheDocument();
  });

  it.each(["healthy", "warning", "critical", "failed", "running", "stopped", "pending", "queued", "completed", "cancelled", "unknown", "degraded", "maintenance"] as const)(
    "renders the %s named state without crashing",
    (state) => {
      render(<StatusIndicator state={state} />);
    },
  );
});
