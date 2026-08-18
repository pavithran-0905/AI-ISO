import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GuardrailNotice } from "@/features/ai-assistant/components/guardrail-notice";

describe("GuardrailNotice", () => {
  it("renders nothing when nothing was filtered", () => {
    const { container } = render(<GuardrailNotice findingsCount={0} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a calm, generic notice when the backend reports guardrail findings", () => {
    render(<GuardrailNotice findingsCount={2} />);

    expect(screen.getByText("Part of this response was filtered for safety")).toBeInTheDocument();
  });

  it("never renders raw guardrail category internals — the component's own API has no channel for them", () => {
    // GuardrailNotice intentionally takes only a count, never the raw
    // `guardrail_findings` strings (e.g. "instruction_override",
    // "private_key") — there is no prop through which a caller could
    // leak them, by construction. This test documents that contract:
    // rendering with any count never produces text matching a raw
    // internal category name.
    render(<GuardrailNotice findingsCount={3} />);

    expect(screen.queryByText(/instruction_override/)).not.toBeInTheDocument();
    expect(screen.queryByText(/private_key/)).not.toBeInTheDocument();
  });
});
