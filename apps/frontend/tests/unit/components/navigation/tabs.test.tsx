import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Tabs } from "@/components/navigation/tabs";

const ITEMS = [
  { id: "one", label: "One" },
  { id: "two", label: "Two" },
  { id: "three", label: "Three" },
];

describe("Tabs", () => {
  it("marks the active tab as selected and gives it tabindex 0", () => {
    render(
      <Tabs items={ITEMS} activeId="two" onChange={() => {}}>
        panel content
      </Tabs>,
    );
    const active = screen.getByRole("tab", { name: "Two" });
    expect(active).toHaveAttribute("aria-selected", "true");
    expect(active).toHaveAttribute("tabindex", "0");

    const inactive = screen.getByRole("tab", { name: "One" });
    expect(inactive).toHaveAttribute("aria-selected", "false");
    expect(inactive).toHaveAttribute("tabindex", "-1");
  });

  it("calls onChange when a tab is clicked", () => {
    const onChange = vi.fn();
    render(
      <Tabs items={ITEMS} activeId="one" onChange={onChange}>
        panel content
      </Tabs>,
    );
    screen.getByRole("tab", { name: "Two" }).click();
    expect(onChange).toHaveBeenCalledWith("two");
  });

  it("moves selection with ArrowRight/ArrowLeft, wrapping at the ends", () => {
    const onChange = vi.fn();
    render(
      <Tabs items={ITEMS} activeId="three" onChange={onChange}>
        panel content
      </Tabs>,
    );
    fireEvent.keyDown(screen.getByRole("tablist"), { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith("one");
  });

  it("renders only the active panel's content", () => {
    render(
      <Tabs items={ITEMS} activeId="one" onChange={() => {}}>
        <p>only this content</p>
      </Tabs>,
    );
    expect(screen.getByRole("tabpanel")).toHaveTextContent("only this content");
  });
});
