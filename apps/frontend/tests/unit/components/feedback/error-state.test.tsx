import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorState } from "@/components/feedback/error-state";

describe("ErrorState", () => {
  it("renders the default title within an alert region", () => {
    render(<ErrorState />);
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong");
  });

  it("calls onRetry when the retry button is clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);

    screen.getByRole("button", { name: "Retry" }).click();

    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("omits the retry button when onRetry is not given", () => {
    render(<ErrorState />);
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });
});
