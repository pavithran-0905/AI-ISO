import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Accordion } from "@/components/navigation/accordion";

const ITEMS = [
  { id: "a", title: "First", content: "First content" },
  { id: "b", title: "Second", content: "Second content", defaultOpen: true },
];

describe("Accordion", () => {
  it("renders every item's title", () => {
    render(<Accordion items={ITEMS} />);
    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
  });

  it("respects defaultOpen per item", () => {
    render(<Accordion items={ITEMS} />);
    const items = document.querySelectorAll("details");
    expect(items[0]).not.toHaveAttribute("open");
    expect(items[1]).toHaveAttribute("open");
  });

  it("toggles open state when the summary is clicked", () => {
    render(<Accordion items={ITEMS} />);
    const firstSummary = screen.getByText("First");
    const firstDetails = firstSummary.closest("details") as HTMLDetailsElement;
    expect(firstDetails.open).toBe(false);

    firstSummary.click();
    expect(firstDetails.open).toBe(true);
  });
});
