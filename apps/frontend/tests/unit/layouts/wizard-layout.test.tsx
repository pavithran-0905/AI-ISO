import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WizardLayout, type WizardStep } from "@/layouts/wizard-layout";

const STEPS: WizardStep[] = [
  { id: "basics", label: "Basics" },
  { id: "details", label: "Details" },
  { id: "review", label: "Review" },
];

describe("WizardLayout", () => {
  it("marks earlier steps complete and the current step with aria-current=step", () => {
    render(
      <WizardLayout steps={STEPS} currentStepId="details" footer={<button>Next</button>}>
        <p>step content</p>
      </WizardLayout>,
    );

    for (const step of STEPS) expect(screen.getByText(step.label)).toBeInTheDocument();
    expect(screen.getByText("Details").closest("li")?.querySelector("[aria-current]")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(screen.getByText("step content")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument();
  });

  it("renders an error indicator and accessible note for a step marked invalid", () => {
    const steps: WizardStep[] = [
      { id: "basics", label: "Basics", status: "invalid" },
      { id: "details", label: "Details" },
    ];

    render(
      <WizardLayout steps={steps} currentStepId="details" footer={null}>
        <p>step content</p>
      </WizardLayout>,
    );

    expect(screen.getByText("(needs attention)")).toBeInTheDocument();
  });
});
