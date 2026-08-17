import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MainLayout } from "@/layouts/main-layout";

describe("MainLayout", () => {
  it("renders header, main content, and footer", () => {
    render(
      <MainLayout>
        <p>page content</p>
      </MainLayout>,
    );

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByText("page content")).toBeInTheDocument();
  });
});
