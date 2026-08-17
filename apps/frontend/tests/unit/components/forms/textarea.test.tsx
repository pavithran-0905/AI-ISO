import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Textarea } from "@/components/forms/textarea";

describe("Textarea", () => {
  it("renders with an accessible label", () => {
    render(<Textarea aria-label="Notes" />);
    expect(screen.getByLabelText("Notes")).toBeInTheDocument();
  });

  it("marks itself invalid via aria-invalid when invalid is set", () => {
    render(<Textarea aria-label="Notes" invalid />);
    expect(screen.getByLabelText("Notes")).toHaveAttribute("aria-invalid", "true");
  });
});
