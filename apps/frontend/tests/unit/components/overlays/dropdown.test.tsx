import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Dropdown } from "@/components/overlays/dropdown";

const ITEMS = [
  { label: "Edit", onSelect: vi.fn() },
  { label: "Delete", destructive: true, onSelect: vi.fn() },
];

describe("Dropdown", () => {
  it("renders menu items when open", () => {
    render(<Dropdown open onClose={() => {}} trigger={<button type="button">Actions</button>} items={ITEMS} />);
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Delete" })).toBeInTheDocument();
  });

  it("calls onSelect and onClose when an item is chosen", () => {
    const onSelect = vi.fn();
    const onClose = vi.fn();
    render(
      <Dropdown
        open
        onClose={onClose}
        trigger={<button type="button">Actions</button>}
        items={[{ label: "Edit", onSelect }]}
      />,
    );
    screen.getByRole("menuitem", { name: "Edit" }).click();
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("moves focus between items with ArrowDown/ArrowUp", () => {
    render(<Dropdown open onClose={() => {}} trigger={<button type="button">Actions</button>} items={ITEMS} />);
    const menu = screen.getByRole("menu");
    const [edit, del] = screen.getAllByRole("menuitem");

    fireEvent.keyDown(menu, { key: "ArrowDown" });
    expect(edit).toHaveFocus();

    fireEvent.keyDown(menu, { key: "ArrowDown" });
    expect(del).toHaveFocus();

    fireEvent.keyDown(menu, { key: "ArrowUp" });
    expect(edit).toHaveFocus();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(<Dropdown open onClose={onClose} trigger={<button type="button">Actions</button>} items={ITEMS} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
