import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardModeTabs } from "@/features/dashboard/components/dashboard-mode-tabs";

describe("DashboardModeTabs", () => {
  it("marks the active mode as checked in an accessible radiogroup", () => {
    render(<DashboardModeTabs mode="executive" onChange={vi.fn()} />);

    expect(screen.getByRole("radiogroup", { name: "Dashboard mode" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Executive" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Operations" })).toHaveAttribute("aria-checked", "false");
  });

  it("calls onChange with the clicked mode", () => {
    const onChange = vi.fn();
    render(<DashboardModeTabs mode="executive" onChange={onChange} />);

    fireEvent.click(screen.getByRole("radio", { name: "Operations" }));
    expect(onChange).toHaveBeenCalledWith("operations");
  });
});
