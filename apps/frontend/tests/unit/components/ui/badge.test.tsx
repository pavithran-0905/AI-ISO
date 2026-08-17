import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge } from "@/components/ui/badge";

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>12</Badge>);
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("applies the outline variant class", () => {
    render(<Badge variant="outline">tag</Badge>);
    expect(screen.getByText("tag")).toHaveClass("border");
  });
});
