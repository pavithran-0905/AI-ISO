import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Drawer } from "@/components/overlays/drawer";

describe("Drawer", () => {
  it("opens with its title when open is true", () => {
    render(<Drawer open onClose={() => {}} title="Edit item" />);
    expect(screen.getByRole("dialog")).toHaveAttribute("open");
    expect(screen.getByText("Edit item")).toBeInTheDocument();
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    render(<Drawer open onClose={onClose} title="Edit item" />);
    screen.getByRole("button", { name: "Close panel" }).click();
    expect(onClose).toHaveBeenCalledOnce();
  });
});
