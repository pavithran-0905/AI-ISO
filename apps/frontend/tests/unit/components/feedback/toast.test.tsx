import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ToastViewport } from "@/components/feedback/toast";
import { toast, useToastStore } from "@/state/toast-store";

describe("ToastViewport", () => {
  afterEach(() => {
    useToastStore.setState({ toasts: [] });
  });

  it("renders nothing when there are no toasts", () => {
    const { container } = render(<ToastViewport />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a pushed toast's title and description", () => {
    toast.success("Saved", "Your changes were saved.");
    render(<ToastViewport />);
    expect(screen.getByText("Saved")).toBeInTheDocument();
    expect(screen.getByText("Your changes were saved.")).toBeInTheDocument();
  });

  it("dismisses a toast when its close button is clicked", () => {
    toast.info("Heads up");
    render(<ToastViewport />);
    // `fireEvent.click` (not the raw DOM `.click()`) so React's state
    // update is flushed inside `act()` before the assertion runs.
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));
    expect(screen.queryByText("Heads up")).not.toBeInTheDocument();
  });
});
