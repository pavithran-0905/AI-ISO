import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FormField } from "@/components/forms/form-field";

describe("FormField", () => {
  it("associates the label with the control via htmlFor/id", () => {
    render(
      <FormField label="Name" required>
        {(fieldProps) => <input {...fieldProps} />}
      </FormField>,
    );
    // Matched by prefix, not exact: the rendered label text is "Name*"
    // (the required asterisk, `aria-hidden` so a screen reader's
    // *computed accessible name* is "Name" alone, but its raw
    // textContent — what an exact string match sees — still includes
    // the glyph).
    expect(screen.getByLabelText(/^Name/)).toBeInTheDocument();
  });

  it("shows an Optional tag when not required", () => {
    render(
      <FormField label="Nickname">{(fieldProps) => <input {...fieldProps} />}</FormField>,
    );
    expect(screen.getByText("Optional")).toBeInTheDocument();
  });

  it("omits the Optional tag when required", () => {
    render(
      <FormField label="Name" required>
        {(fieldProps) => <input {...fieldProps} />}
      </FormField>,
    );
    expect(screen.queryByText("Optional")).not.toBeInTheDocument();
  });

  it("wires aria-describedby to the description", () => {
    render(
      <FormField label="Name" description="Shown publicly.">
        {(fieldProps) => <input {...fieldProps} />}
      </FormField>,
    );
    const input = screen.getByLabelText("Name");
    expect(input.getAttribute("aria-describedby")).toContain("description");
    expect(screen.getByText("Shown publicly.")).toBeInTheDocument();
  });

  it("wires aria-describedby and aria-invalid to the error, hiding the description", () => {
    render(
      <FormField label="Name" description="Shown publicly." error="Name is required.">
        {(fieldProps) => <input {...fieldProps} />}
      </FormField>,
    );
    const input = screen.getByLabelText("Name");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-describedby")).toContain("error");
    expect(screen.getByRole("alert")).toHaveTextContent("Name is required.");
    expect(screen.queryByText("Shown publicly.")).not.toBeInTheDocument();
  });
});
