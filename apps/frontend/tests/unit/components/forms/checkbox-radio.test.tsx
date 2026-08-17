import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Checkbox } from "@/components/forms/checkbox";
import { Radio } from "@/components/forms/radio";

describe("Checkbox", () => {
  it("toggles checked state on click", () => {
    render(<Checkbox aria-label="Agree" />);
    const checkbox = screen.getByLabelText("Agree") as HTMLInputElement;
    expect(checkbox.checked).toBe(false);
    checkbox.click();
    expect(checkbox.checked).toBe(true);
  });
});

describe("Radio", () => {
  it("selects only one option within a group", () => {
    render(
      <>
        <Radio name="choice" aria-label="A" />
        <Radio name="choice" aria-label="B" />
      </>,
    );
    const a = screen.getByLabelText("A") as HTMLInputElement;
    const b = screen.getByLabelText("B") as HTMLInputElement;

    a.click();
    expect(a.checked).toBe(true);

    b.click();
    expect(a.checked).toBe(false);
    expect(b.checked).toBe(true);
  });
});
