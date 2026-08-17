import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PartialDataNotice } from "@/components/feedback/partial-data-notice";

describe("PartialDataNotice", () => {
  it("renders the given message within a status region", () => {
    render(<PartialDataNotice message="Showing 3 of 4 regions — 1 failed to load." />);
    expect(screen.getByRole("status")).toHaveTextContent("Showing 3 of 4 regions");
  });
});
