import { render, screen } from "@testing-library/react";
import { CheckCircle2 } from "lucide-react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/components/feedback/status-badge";

describe("StatusBadge", () => {
  it.each([
    ["success", "Healthy"],
    ["warning", "Degraded"],
    ["danger", "Unreachable"],
    ["neutral", "Unknown"],
    ["info", "Informational"],
    ["pending", "Pending"],
    ["running", "Running"],
    ["stopped", "Stopped"],
    ["degraded", "Degraded"],
    ["unknown", "Unknown"],
  ] as const)("renders the %s tone with its label", (tone, label) => {
    render(<StatusBadge tone={tone} label={label} />);

    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("renders a decorative dot when no icon is given", () => {
    const { container } = render(<StatusBadge tone="success" label="Healthy" />);
    expect(container.querySelector('[aria-hidden="true"]')).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeInTheDocument();
  });

  it("renders the given icon instead of the dot when provided", () => {
    const { container } = render(<StatusBadge tone="success" label="Healthy" icon={CheckCircle2} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
