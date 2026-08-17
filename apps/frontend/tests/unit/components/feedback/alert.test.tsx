import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Alert } from "@/components/feedback/alert";

describe("Alert", () => {
  it("renders the title and children", () => {
    render(<Alert title="Heads up">Some detail.</Alert>);
    expect(screen.getByText("Heads up")).toBeInTheDocument();
    expect(screen.getByText("Some detail.")).toBeInTheDocument();
  });

  it("uses an assertive alert role for danger/warning tones", () => {
    render(<Alert tone="danger" title="Failed" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("uses a polite status role for info/success tones", () => {
    render(<Alert tone="info" title="FYI" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
