import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Select } from "@/components/forms/select";

describe("Select", () => {
  it("renders its options and responds to selection", () => {
    render(
      <Select aria-label="Region" defaultValue="us-east-1">
        <option value="us-east-1">us-east-1</option>
        <option value="eu-west-1">eu-west-1</option>
      </Select>,
    );

    const select = screen.getByLabelText("Region") as HTMLSelectElement;
    expect(select.value).toBe("us-east-1");

    fireEvent.change(select, { target: { value: "eu-west-1" } });
    expect(select.value).toBe("eu-west-1");
  });
});
