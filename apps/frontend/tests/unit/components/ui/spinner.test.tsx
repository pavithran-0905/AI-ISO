import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Spinner } from "@/components/ui/spinner";

describe("Spinner", () => {
  it("renders as decorative (hidden from screen readers)", () => {
    const { container } = render(<Spinner />);
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("respects the size prop", () => {
    const { container } = render(<Spinner size="feature" />);
    expect(container.querySelector("svg")).toHaveClass("size-8");
  });
});
