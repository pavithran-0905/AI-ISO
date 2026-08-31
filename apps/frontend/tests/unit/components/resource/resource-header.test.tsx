import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResourceHeader } from "@/components/resource/resource-header";

describe("ResourceHeader", () => {
  it("renders the title, resource type, and status badges", () => {
    render(<ResourceHeader title="edge-01" resourceType="physical_server" statusBadges={<span>Healthy</span>} />);
    expect(screen.getByRole("heading", { name: "edge-01" })).toBeInTheDocument();
    expect(screen.getByText("physical_server")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });

  it("omits the meta row entirely when no identifier, environment, or timestamp is available", () => {
    const { container } = render(<ResourceHeader title="edge-01" />);
    expect(container.querySelector(".font-mono")).not.toBeInTheDocument();
  });

  it("shows identifier, environment, and a relative last-updated time when provided", () => {
    render(<ResourceHeader title="edge-01" identifier="edge-01.internal" environment="production" lastUpdatedAt={new Date().toISOString()} />);
    expect(screen.getByText("edge-01.internal")).toBeInTheDocument();
    expect(screen.getByText("production")).toBeInTheDocument();
    expect(screen.getByText(/Updated/)).toBeInTheDocument();
  });

  it("renders primary and secondary actions", () => {
    render(<ResourceHeader title="edge-01" primaryAction={<button>Edit</button>} secondaryActions={<button>Refresh</button>} />);
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
  });
});
