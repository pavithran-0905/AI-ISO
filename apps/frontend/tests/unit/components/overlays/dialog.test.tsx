import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Dialog } from "@/components/overlays/dialog";

describe("Dialog", () => {
  it("is not open when open is false", () => {
    render(<Dialog open={false} onClose={() => {}} title="Confirm" />);
    expect(screen.getByRole("dialog", { hidden: true })).not.toHaveAttribute("open");
  });

  it("opens as a modal when open is true", () => {
    render(<Dialog open onClose={() => {}} title="Confirm" description="Are you sure?" />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("open");
    expect(screen.getByText("Confirm")).toBeInTheDocument();
    expect(screen.getByText("Are you sure?")).toBeInTheDocument();
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    render(<Dialog open onClose={onClose} title="Confirm" />);
    screen.getByRole("button", { name: "Close dialog" }).click();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders footer content", () => {
    render(<Dialog open onClose={() => {}} title="Confirm" footer={<button type="button">Confirm</button>} />);
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
  });
});
