import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Popover } from "@/components/overlays/popover";

describe("Popover", () => {
  it("does not render content when closed", () => {
    render(<Popover open={false} onClose={() => {}} trigger={<button type="button">Open</button>}>content</Popover>);
    expect(screen.queryByText("content")).not.toBeInTheDocument();
  });

  it("renders content when open", () => {
    render(
      <Popover open onClose={() => {}} trigger={<button type="button">Open</button>}>
        content
      </Popover>,
    );
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("calls onClose on Escape", () => {
    const onClose = vi.fn();
    render(
      <Popover open onClose={onClose} trigger={<button type="button">Open</button>}>
        content
      </Popover>,
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose on an outside click", () => {
    const onClose = vi.fn();
    render(
      <div>
        <Popover open onClose={onClose} trigger={<button type="button">Open</button>}>
          content
        </Popover>
        <button type="button">outside</button>
      </div>,
    );
    fireEvent.pointerDown(screen.getByText("outside"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
