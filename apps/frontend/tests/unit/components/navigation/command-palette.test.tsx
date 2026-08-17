import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CommandPalette } from "@/components/navigation/command-palette";
import { useCommandPaletteStore } from "@/state/command-palette-store";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

describe("CommandPalette", () => {
  afterEach(() => {
    useCommandPaletteStore.setState({ open: false });
    push.mockClear();
  });

  it("opens in response to the shared store's open flag", () => {
    render(<CommandPalette />);
    expect(screen.getByRole("dialog", { hidden: true })).not.toHaveAttribute("open");

    act(() => {
      useCommandPaletteStore.getState().show();
    });
    expect(screen.getByRole("dialog", { hidden: true })).toHaveAttribute("open");
  });

  it("opens on Ctrl/Cmd+K from anywhere in the document", () => {
    render(<CommandPalette />);
    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    expect(useCommandPaletteStore.getState().open).toBe(true);
  });

  it("lists every implemented route by default and filters as the query changes", () => {
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    expect(screen.getByRole("option", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /design system showcase/i })).toBeInTheDocument();

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "design" } });

    expect(screen.queryByRole("option", { name: /^dashboard/i })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: /design system showcase/i })).toBeInTheDocument();
  });

  it("shows an empty state when no command matches the query", () => {
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "nothing matches this" } });
    expect(screen.getByText("No matching pages")).toBeInTheDocument();
  });

  it("navigates to the highlighted result and closes on Enter", () => {
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "design" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(push).toHaveBeenCalledWith("/design-system");
    expect(useCommandPaletteStore.getState().open).toBe(false);
  });

  it("moves the active option with ArrowDown/ArrowUp", () => {
    useCommandPaletteStore.setState({ open: true });
    render(<CommandPalette />);

    const input = screen.getByRole("combobox");
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(options[1]).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(options[0]).toHaveAttribute("aria-selected", "true");
  });
});
