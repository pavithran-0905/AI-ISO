import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SplitPaneLayout } from "@/layouts/split-pane-layout";

describe("SplitPaneLayout", () => {
  it("renders both panes and a resize separator", () => {
    render(<SplitPaneLayout start={<p>list</p>} end={<p>detail</p>} />);

    expect(screen.getByText("list")).toBeInTheDocument();
    expect(screen.getByText("detail")).toBeInTheDocument();
    expect(screen.getByRole("separator")).toBeInTheDocument();
  });

  it("widens the start pane when ArrowRight is pressed on the separator", () => {
    render(
      <SplitPaneLayout start={<p>list</p>} end={<p>detail</p>} defaultSplitPercent={40} />,
    );

    const separator = screen.getByRole("separator");
    const startPane = screen.getByText("list").parentElement as HTMLElement;
    const before = startPane.style.flexBasis;

    fireEvent.keyDown(separator, { key: "ArrowRight" });

    expect(startPane.style.flexBasis).not.toBe(before);
  });
});
