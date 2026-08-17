import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OfflineState } from "@/components/feedback/offline-state";

describe("OfflineState", () => {
  it("renders the offline message within an alert region", () => {
    render(<OfflineState />);
    expect(screen.getByRole("alert")).toHaveTextContent("You're offline");
  });

  it("calls onRetry when the retry button is clicked", () => {
    const onRetry = vi.fn();
    render(<OfflineState onRetry={onRetry} />);

    screen.getByRole("button", { name: "Retry" }).click();

    expect(onRetry).toHaveBeenCalledOnce();
  });
});
