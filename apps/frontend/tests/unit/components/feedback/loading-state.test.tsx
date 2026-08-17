import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LoadingState } from "@/components/feedback/loading-state";

describe("LoadingState", () => {
  it("announces the default label via a status region", () => {
    render(<LoadingState />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading…");
  });

  it("renders a custom label", () => {
    render(<LoadingState label="Checking gateway status" />);
    expect(screen.getByRole("status")).toHaveTextContent("Checking gateway status");
  });
});
