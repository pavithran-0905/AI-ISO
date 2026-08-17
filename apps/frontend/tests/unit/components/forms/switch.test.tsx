import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Switch } from "@/components/forms/switch";

describe("Switch", () => {
  it("renders as a real switch role", () => {
    render(<Switch aria-label="Enable feature" />);
    expect(screen.getByRole("switch", { name: "Enable feature" })).toBeInTheDocument();
  });

  it("calls onChange when toggled", () => {
    const onChange = vi.fn();
    render(<Switch aria-label="Enable feature" onChange={onChange} />);
    screen.getByRole("switch").click();
    expect(onChange).toHaveBeenCalledOnce();
  });

  it("reflects the checked prop", () => {
    render(<Switch aria-label="Enable feature" checked readOnly />);
    expect(screen.getByRole("switch")).toBeChecked();
  });
});
