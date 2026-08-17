import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Skeleton } from "@/components/feedback/skeleton";

describe("Skeleton", () => {
  it("renders as a decorative, screen-reader-hidden block", () => {
    const { container } = render(<Skeleton className="h-4 w-full" />);
    const el = container.firstElementChild;
    expect(el).toHaveAttribute("aria-hidden", "true");
    expect(el).toHaveClass("h-4", "w-full");
  });
});
