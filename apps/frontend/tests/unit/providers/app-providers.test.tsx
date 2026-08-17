import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppProviders } from "@/providers/app-providers";

// AppProviders mounts CommandPalette (docs/frontend Prompt 003 §15),
// which calls next/navigation's useRouter — unavailable outside a real
// Next.js app router context, so it's mocked here the same way
// auth/guards.test.tsx already mocks it.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

describe("AppProviders", () => {
  it("renders children without crashing", () => {
    render(
      <AppProviders>
        <p>content</p>
      </AppProviders>,
    );

    expect(screen.getByText("content")).toBeInTheDocument();
  });
});
