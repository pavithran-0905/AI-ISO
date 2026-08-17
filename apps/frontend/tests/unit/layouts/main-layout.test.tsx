import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MainLayout } from "@/layouts/main-layout";
import { TestQueryProvider } from "../../query-test-utils";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

describe("MainLayout", () => {
  it("renders header, primary navigation, breadcrumbs, content, and footer", () => {
    render(
      <TestQueryProvider>
        <MainLayout>
          <p>page content</p>
        </MainLayout>
      </TestQueryProvider>,
    );

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByText("page content")).toBeInTheDocument();
  });

  it("marks the current route's breadcrumb as the current page", () => {
    render(
      <TestQueryProvider>
        <MainLayout>
          <p>page content</p>
        </MainLayout>
      </TestQueryProvider>,
    );

    const breadcrumbNav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(breadcrumbNav).getByText("Dashboard")).toHaveAttribute("aria-current", "page");
  });
});
