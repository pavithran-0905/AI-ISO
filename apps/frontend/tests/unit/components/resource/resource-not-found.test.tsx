import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResourceNotFound } from "@/components/resource/resource-not-found";

describe("ResourceNotFound", () => {
  it("shows a dedicated not-found message with the real resource label", () => {
    render(<ResourceNotFound resourceLabel="Asset" backHref="/infrastructure/assets" backLabel="Back to Assets" />);
    expect(screen.getByText("Asset not found")).toBeInTheDocument();
  });

  it("provides Back and Search actions, per §29", () => {
    render(<ResourceNotFound resourceLabel="Asset" backHref="/infrastructure/assets" backLabel="Back to Assets" />);
    expect(screen.getByRole("link", { name: "Back to Assets" })).toHaveAttribute("href", "/infrastructure/assets");
    expect(screen.getByRole("link", { name: "Search" })).toHaveAttribute("href", "/search");
  });
});
