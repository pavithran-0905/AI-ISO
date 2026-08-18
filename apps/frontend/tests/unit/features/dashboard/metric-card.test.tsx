import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricCard } from "@/features/dashboard/components/metric-card";

describe("MetricCard", () => {
  it("renders the label, value, and description", () => {
    render(<MetricCard label="Users" value={42} description="Active accounts" />);

    expect(screen.getByText("Users")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Active accounts")).toBeInTheDocument();
  });

  it("renders as a plain card with no link when href is omitted", () => {
    render(<MetricCard label="Users" value={42} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders as a real link to an existing route when href is given", () => {
    render(<MetricCard label="Assets" value={7} href="/monitoring" />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/monitoring");
  });
});
