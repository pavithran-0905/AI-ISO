import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { UserTable } from "@/features/administration/components/user-table";
import type { UserSearchResult } from "@/features/administration/types";

const ONE_USER = { id: "u1", username: "sarun", email: "sarun@example.com", displayName: "Sarun", avatar: null, status: "active" as const, createdAt: "2026-01-01T00:00:00Z" };

describe("UserTable", () => {
  it("disables Next when hasMore is false, since no real total count exists to page against", () => {
    const result: UserSearchResult = { items: [ONE_USER], page: 1, pageSize: 25, hasMore: false };
    render(<UserTable result={result} onPageChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("enables Next when hasMore is true, and calls onPageChange with the next page", () => {
    const result: UserSearchResult = { items: [ONE_USER], page: 1, pageSize: 25, hasMore: true };
    const onPageChange = vi.fn();
    render(<UserTable result={result} onPageChange={onPageChange} />);

    const nextButton = screen.getByRole("button", { name: "Next" });
    expect(nextButton).not.toBeDisabled();
    fireEvent.click(nextButton);
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("disables Previous on the first page", () => {
    const result: UserSearchResult = { items: [ONE_USER], page: 1, pageSize: 25, hasMore: true };
    render(<UserTable result={result} onPageChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });
});
