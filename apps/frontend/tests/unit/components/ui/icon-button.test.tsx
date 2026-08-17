import { render, screen } from "@testing-library/react";
import { Trash2 } from "lucide-react";
import { describe, expect, it, vi } from "vitest";

import { IconButton } from "@/components/ui/icon-button";

describe("IconButton", () => {
  it("requires and renders an accessible name", () => {
    render(<IconButton icon={Trash2} aria-label="Delete item" />);
    expect(screen.getByRole("button", { name: "Delete item" })).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<IconButton icon={Trash2} aria-label="Delete" onClick={onClick} />);
    screen.getByRole("button").click();
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("disables and marks busy while loading", () => {
    render(<IconButton icon={Trash2} aria-label="Delete" loading />);
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });
});
