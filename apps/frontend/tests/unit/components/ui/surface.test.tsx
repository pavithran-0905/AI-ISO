import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Surface } from "@/components/ui/surface";

describe("Surface", () => {
  it("renders children with the flat elevation by default", () => {
    render(<Surface data-testid="surface">content</Surface>);
    expect(screen.getByTestId("surface")).toHaveClass("border");
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("applies overlay elevation classes", () => {
    render(
      <Surface elevation="overlay" data-testid="surface">
        content
      </Surface>,
    );
    expect(screen.getByTestId("surface")).toHaveClass("shadow-elevation-3");
  });
});
