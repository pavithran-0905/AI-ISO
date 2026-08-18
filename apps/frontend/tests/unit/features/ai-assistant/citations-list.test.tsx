import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CitationsList } from "@/features/ai-assistant/components/citations-list";
import type { Citation } from "@/features/ai-assistant/types";

describe("CitationsList", () => {
  it("renders nothing when a response drew on no sources", () => {
    const { container } = render(<CitationsList citations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a linked source when a citation has a real uri", () => {
    const citation: Citation = { chunkId: "ch1", documentId: "d1", title: "Runbook: disk pressure", uri: "https://wiki.internal/runbooks/disk", score: 0.87 };
    render(<CitationsList citations={[citation]} />);

    const link = screen.getByRole("link", { name: "Runbook: disk pressure" });
    expect(link).toHaveAttribute("href", "https://wiki.internal/runbooks/disk");
    expect(screen.getByText("(87%)")).toBeInTheDocument();
  });

  it("renders a plain (unlinked) title when a citation has no uri, rather than a dead link", () => {
    const citation: Citation = { chunkId: "ch2", documentId: "d2", title: "Ingested incident notes", uri: null, score: 0.6 };
    render(<CitationsList citations={[citation]} />);

    expect(screen.getByText("Ingested incident notes")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
