import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AuthLayout } from "@/layouts/auth-layout";

describe("AuthLayout", () => {
  it("renders the brand and children centered", () => {
    render(
      <AuthLayout>
        <p>login form</p>
      </AuthLayout>,
    );

    expect(screen.getByText("AI-IOS")).toBeInTheDocument();
    expect(screen.getByText("login form")).toBeInTheDocument();
  });
});
