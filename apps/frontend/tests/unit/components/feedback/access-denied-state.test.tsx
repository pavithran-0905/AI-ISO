import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AccessDeniedState } from "@/components/feedback/access-denied-state";

describe("AccessDeniedState", () => {
  it("renders unauthorized copy for the unauthorized variant", () => {
    render(<AccessDeniedState variant="unauthorized" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Sign in required");
  });

  it("renders forbidden copy for the forbidden variant", () => {
    render(<AccessDeniedState variant="forbidden" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Access denied");
  });

  it("renders an optional action", () => {
    render(<AccessDeniedState variant="forbidden" action={<button type="button">Home</button>} />);
    expect(screen.getByRole("button", { name: "Home" })).toBeInTheDocument();
  });
});
