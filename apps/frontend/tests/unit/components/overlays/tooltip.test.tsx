import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Tooltip } from "@/components/overlays/tooltip";

describe("Tooltip", () => {
  it("wires aria-describedby from the trigger to the tooltip bubble", () => {
    render(
      <Tooltip label="Delete this item">
        <button type="button">Delete</button>
      </Tooltip>,
    );

    const trigger = screen.getByRole("button", { name: "Delete" });
    const tooltip = screen.getByRole("tooltip", { hidden: true });
    expect(trigger.getAttribute("aria-describedby")).toBe(tooltip.id);
    expect(tooltip).toHaveTextContent("Delete this item");
  });
});
