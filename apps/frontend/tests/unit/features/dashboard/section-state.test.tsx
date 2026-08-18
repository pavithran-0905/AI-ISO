import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/api/client";
import { SectionState } from "@/features/dashboard/components/section-state";

describe("SectionState", () => {
  it("shows a loading skeleton while loading", () => {
    render(
      <SectionState isLoading isError={false}>
        <p>content</p>
      </SectionState>,
    );

    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(screen.queryByText("content")).not.toBeInTheDocument();
  });

  it("shows a retryable error state for a generic failure", () => {
    const onRetry = vi.fn();
    render(
      <SectionState isLoading={false} isError error={new Error("boom")} onRetry={onRetry}>
        <p>content</p>
      </SectionState>,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("shows a permission-safe state (not a generic error) for a 403", () => {
    render(
      <SectionState isLoading={false} isError error={new ApiRequestError(403, "forbidden", "X", [])}>
        <p>content</p>
      </SectionState>,
    );

    expect(screen.getByText("Access denied")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("renders children once loaded without error", () => {
    render(
      <SectionState isLoading={false} isError={false}>
        <p>content</p>
      </SectionState>,
    );

    expect(screen.getByText("content")).toBeInTheDocument();
  });
});
