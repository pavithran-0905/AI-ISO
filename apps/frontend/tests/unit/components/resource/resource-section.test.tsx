import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ResourceSection } from "@/components/resource/resource-section";

describe("ResourceSection", () => {
  it("renders its title and children when no query state is passed", () => {
    render(
      <ResourceSection title="Identity">
        <p>Real content</p>
      </ResourceSection>,
    );
    expect(screen.getByText("Identity")).toBeInTheDocument();
    expect(screen.getByText("Real content")).toBeInTheDocument();
  });

  it("shows a loading skeleton instead of children while its own query is loading", () => {
    render(
      <ResourceSection title="Relationships" isLoading isError={false}>
        <p>Should not render yet</p>
      </ResourceSection>,
    );
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(screen.queryByText("Should not render yet")).not.toBeInTheDocument();
  });

  it("shows a retry-capable error state on its own failure, independent of other sections (§28)", () => {
    const onRetry = vi.fn();
    render(
      <ResourceSection title="Alerts" isLoading={false} isError onRetry={onRetry}>
        <p>Should not render</p>
      </ResourceSection>,
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.queryByText("Should not render")).not.toBeInTheDocument();
  });

  it("renders an optional header action alongside the title", () => {
    render(
      <ResourceSection title="Topology" action={<button>Open in Topology</button>}>
        <p>content</p>
      </ResourceSection>,
    );
    expect(screen.getByRole("button", { name: "Open in Topology" })).toBeInTheDocument();
  });
});
