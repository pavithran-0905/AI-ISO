import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Separator } from "@/components/ui/separator";

describe("Separator", () => {
  it("renders as a horizontal separator by default", () => {
    render(<Separator />);
    expect(screen.getByRole("separator")).toHaveAttribute("aria-orientation", "horizontal");
  });

  it("renders as a vertical separator", () => {
    render(<Separator orientation="vertical" />);
    expect(screen.getByRole("separator")).toHaveAttribute("aria-orientation", "vertical");
  });
});
