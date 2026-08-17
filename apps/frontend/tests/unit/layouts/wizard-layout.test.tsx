import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WizardLayout } from "@/layouts/wizard-layout";

const STEPS = [
  { id: "one", label: "Step One" },
  { id: "two", label: "Step Two" },
  { id: "three", label: "Step Three" },
];

describe("WizardLayout", () => {
  it("renders every step label, content, and footer", () => {
    render(
      <WizardLayout steps={STEPS} currentStepId="two" footer={<button type="button">Next</button>}>
        <p>step content</p>
      </WizardLayout>,
    );

    for (const step of STEPS) expect(screen.getByText(step.label)).toBeInTheDocument();
    expect(screen.getByText("step content")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument();
  });

  it("marks the current step with aria-current", () => {
    render(
      <WizardLayout steps={STEPS} currentStepId="two" footer={null}>
        <p>content</p>
      </WizardLayout>,
    );

    expect(screen.getByText("2")).toHaveAttribute("aria-current", "step");
  });
});
