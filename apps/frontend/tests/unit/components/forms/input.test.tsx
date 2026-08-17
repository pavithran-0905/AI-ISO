import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Input } from "@/components/forms/input";

describe("Input", () => {
  it("renders and accepts typed input", async () => {
    render(<Input aria-label="Name" />);
    const input = screen.getByLabelText("Name") as HTMLInputElement;
    input.focus();
    expect(input).toHaveFocus();
  });

  it("marks itself invalid via aria-invalid when invalid is set", () => {
    render(<Input aria-label="Name" invalid />);
    expect(screen.getByLabelText("Name")).toHaveAttribute("aria-invalid", "true");
  });

  it("does not set aria-invalid by default", () => {
    render(<Input aria-label="Name" />);
    expect(screen.getByLabelText("Name")).not.toHaveAttribute("aria-invalid");
  });

  it("respects the disabled state", () => {
    render(<Input aria-label="Name" disabled />);
    expect(screen.getByLabelText("Name")).toBeDisabled();
  });
});
