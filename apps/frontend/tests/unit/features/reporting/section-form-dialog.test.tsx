import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SectionFormDialog } from "@/features/reporting/components/section-form-dialog";

describe("SectionFormDialog", () => {
  it("rejects a table section with no query or columns, matching the backend's own per-kind validation", () => {
    const onSave = vi.fn();
    render(<SectionFormDialog section={null} open onClose={vi.fn()} onSave={onSave} />);

    fireEvent.change(screen.getByLabelText("Key"), { target: { value: "assets" } });
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "table" } });
    fireEvent.click(screen.getByRole("button", { name: "Save section" }));

    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByText(/requires a query and at least one column/)).toBeInTheDocument();
  });

  it("rejects a heading section with no text", () => {
    const onSave = vi.fn();
    render(<SectionFormDialog section={null} open onClose={vi.fn()} onSave={onSave} />);

    fireEvent.change(screen.getByLabelText("Key"), { target: { value: "intro" } });
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "heading" } });
    fireEvent.click(screen.getByRole("button", { name: "Save section" }));

    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByText(/requires text/)).toBeInTheDocument();
  });

  it("saves a valid text section", () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(<SectionFormDialog section={null} open onClose={onClose} onSave={onSave} />);

    fireEvent.change(screen.getByLabelText("Key"), { target: { value: "intro" } });
    fireEvent.change(screen.getByLabelText("Text (static prose or Jinja2)"), { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Save section" }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ key: "intro", kind: "text", text: "Hello" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("pre-fills from an existing section when editing", () => {
    render(
      <SectionFormDialog
        section={{ key: "intro", kind: "text", text: "Existing", columns: [] }}
        open
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Key")).toHaveValue("intro");
    expect(screen.getByLabelText("Text (static prose or Jinja2)")).toHaveValue("Existing");
  });
});
