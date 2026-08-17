import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "@/components/feedback/empty-state";

describe("EmptyState", () => {
  it("renders title, description, and action", () => {
    render(
      <EmptyState
        title="No items yet"
        description="Create your first item to get started."
        action={<button type="button">Create</button>}
      />,
    );

    expect(screen.getByText("No items yet")).toBeInTheDocument();
    expect(screen.getByText("Create your first item to get started.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create" })).toBeInTheDocument();
  });

  it("renders without an optional description or action", () => {
    render(<EmptyState title="No items yet" />);
    expect(screen.getByText("No items yet")).toBeInTheDocument();
  });
});
