"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import { Button } from "@/components/ui/button";
import { useIngestDocument } from "@/features/ai-assistant/hooks/use-knowledge";
import { DOCUMENT_SOURCE_TYPES, type DocumentSourceTypeValue } from "@/features/ai-assistant/types";
import { toast } from "@/state/toast-store";

/**
 * A simple text-based ingest form (§24-adjacent affordance) — title,
 * source type, and raw text only. No file upload: `DocumentIngestRequest`
 * has no file field, only `text: str` (see
 * `docs/frontend/backend-v1-integration-limitations.md`), so a file
 * picker here would promise something the backend cannot accept.
 */
export function IngestDocumentForm({ organizationId }: { organizationId: string }) {
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<DocumentSourceTypeValue>("uploaded");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const ingestDocument = useIngestDocument();

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim() || !text.trim()) {
      setError("Title and text are required.");
      return;
    }
    setError(null);
    try {
      const result = await ingestDocument.mutateAsync({ organizationId, sourceType, title: title.trim(), text: text.trim() });
      toast.success(
        result.skippedUnchanged ? "Document already up to date" : "Document ingested",
        result.skippedUnchanged ? undefined : `${result.chunksCreated} chunk(s) created.`,
      );
      setTitle("");
      setText("");
    } catch (submitError) {
      const description = submitError instanceof ApiRequestError ? submitError.message : "Please try again.";
      toast.danger("Could not ingest document", description);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="ingest-title">Title</Label>
        <Input id="ingest-title" value={title} onChange={(event) => setTitle(event.target.value)} required />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="ingest-source-type">Source type</Label>
        <Select id="ingest-source-type" value={sourceType} onChange={(event) => setSourceType(event.target.value as DocumentSourceTypeValue)}>
          {DOCUMENT_SOURCE_TYPES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="ingest-text">Text</Label>
        <Textarea id="ingest-text" value={text} onChange={(event) => setText(event.target.value)} rows={8} required />
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}

      <Button type="submit" loading={ingestDocument.isPending} className="w-fit">
        Ingest document
      </Button>
    </form>
  );
}
