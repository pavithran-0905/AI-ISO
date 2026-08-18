import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportDefinitionEditor } from "@/features/reporting/components/report-definition-editor";
import type { ReportDefinition } from "@/features/reporting/types";

const DEFINITION: ReportDefinition = {
  title: "Weekly report",
  sections: [
    { key: "intro", kind: "heading", title: "Intro", text: "Hi" },
    { key: "details", kind: "text", title: "Details", text: "More" },
  ],
};

describe("ReportDefinitionEditor", () => {
  it("renders every real section with its kind", () => {
    render(<ReportDefinitionEditor definition={DEFINITION} onChange={vi.fn()} />);

    expect(screen.getByText("Intro")).toBeInTheDocument();
    expect(screen.getByText("heading")).toBeInTheDocument();
    expect(screen.getByText("Details")).toBeInTheDocument();
  });

  it("removes a section", () => {
    const onChange = vi.fn();
    render(<ReportDefinitionEditor definition={DEFINITION} onChange={onChange} />);

    fireEvent.click(screen.getAllByRole("button", { name: "Remove section" })[0]);

    expect(onChange).toHaveBeenCalledWith({ ...DEFINITION, sections: [DEFINITION.sections[1]] });
  });

  it("reorders a section downward", () => {
    const onChange = vi.fn();
    render(<ReportDefinitionEditor definition={DEFINITION} onChange={onChange} />);

    fireEvent.click(screen.getAllByRole("button", { name: "↓" })[0]);

    expect(onChange).toHaveBeenCalledWith({ ...DEFINITION, sections: [DEFINITION.sections[1], DEFINITION.sections[0]] });
  });

  it("disables moving the first section up and the last section down", () => {
    render(<ReportDefinitionEditor definition={DEFINITION} onChange={vi.fn()} />);

    const upButtons = screen.getAllByRole("button", { name: "↑" });
    const downButtons = screen.getAllByRole("button", { name: "↓" });
    expect(upButtons[0]).toBeDisabled();
    expect(downButtons[1]).toBeDisabled();
  });

  it("opens the add-section dialog", () => {
    render(<ReportDefinitionEditor definition={DEFINITION} onChange={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Add section" }));

    expect(screen.getByRole("heading", { name: "Add section" })).toBeInTheDocument();
  });
});
