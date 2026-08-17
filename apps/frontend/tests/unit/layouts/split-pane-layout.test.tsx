import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SplitPaneLayout } from "@/layouts/split-pane-layout";

describe("SplitPaneLayout", () => {
  it("renders both panes and exposes the divider as a labeled, valued separator", () => {
    render(<SplitPaneLayout start={<p>list</p>} end={<p>detail</p>} defaultSplitPercent={40} />);

    expect(screen.getByText("list")).toBeInTheDocument();
    expect(screen.getByText("detail")).toBeInTheDocument();

    const separator = screen.getByRole("separator", { name: "Resize panels" });
    expect(separator).toHaveAttribute("aria-orientation", "vertical");
    expect(separator).toHaveAttribute("aria-valuenow", "40");
    expect(separator).toHaveAttribute("aria-valuemin", "20");
    expect(separator).toHaveAttribute("aria-valuemax", "80");
  });

  it("resizes with ArrowLeft/ArrowRight and jumps to the bounds with Home/End", () => {
    render(<SplitPaneLayout start={<p>list</p>} end={<p>detail</p>} defaultSplitPercent={40} />);
    const separator = screen.getByRole("separator", { name: "Resize panels" });

    fireEvent.keyDown(separator, { key: "ArrowRight" });
    expect(separator).toHaveAttribute("aria-valuenow", "42");

    fireEvent.keyDown(separator, { key: "ArrowLeft" });
    fireEvent.keyDown(separator, { key: "ArrowLeft" });
    expect(separator).toHaveAttribute("aria-valuenow", "38");

    fireEvent.keyDown(separator, { key: "End" });
    expect(separator).toHaveAttribute("aria-valuenow", "80");

    fireEvent.keyDown(separator, { key: "Home" });
    expect(separator).toHaveAttribute("aria-valuenow", "20");
  });
});
