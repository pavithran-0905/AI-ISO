/**
 * `services/ai-assistant-service/app/api/knowledge.py` — confirmed by
 * source inspection. Retrieval here uses the exact same `RagPipeline`
 * `/ai/chat` uses internally, so a search here is a genuine preview of
 * what the assistant would find for a similar question — not a
 * disconnected demo endpoint.
 */

import { apiClient } from "@/api/client";
import type {
  DocumentSourceTypeValue,
  IngestDocumentInput,
  IngestDocumentResult,
  KnowledgeDocument,
  KnowledgeSearchHit,
  KnowledgeSearchInput,
} from "@/features/ai-assistant/types";

interface DocumentResponseBody {
  id: string;
  organization_id: string;
  source_type: DocumentSourceTypeValue;
  external_id: string | null;
  title: string;
  uri: string | null;
  content_hash: string;
  document_metadata: Record<string, unknown>;
}

interface DocumentIngestResponseBody {
  document_id: string;
  title: string;
  chunks_created: number;
  skipped_unchanged: boolean;
}

interface KnowledgeSearchHitBody {
  chunk_id: string;
  document_id: string;
  document_title: string;
  document_uri: string | null;
  content: string;
  score: number;
}

function toDocument(body: DocumentResponseBody): KnowledgeDocument {
  return {
    id: body.id,
    organizationId: body.organization_id,
    sourceType: body.source_type,
    externalId: body.external_id,
    title: body.title,
    uri: body.uri,
    contentHash: body.content_hash,
  };
}

function toSearchHit(body: KnowledgeSearchHitBody): KnowledgeSearchHit {
  return {
    chunkId: body.chunk_id,
    documentId: body.document_id,
    documentTitle: body.document_title,
    documentUri: body.document_uri,
    content: body.content,
    score: body.score,
  };
}

export const knowledgeApi = {
  async listDocuments(organizationId: string): Promise<KnowledgeDocument[]> {
    const body = await apiClient.get<DocumentResponseBody[]>(
      `/ai/knowledge/documents?organization_id=${encodeURIComponent(organizationId)}`,
    );
    return body.map(toDocument);
  },

  async ingest(input: IngestDocumentInput): Promise<IngestDocumentResult> {
    const body = await apiClient.post<DocumentIngestResponseBody>("/ai/knowledge/documents", {
      organization_id: input.organizationId,
      project_id: input.projectId,
      source_type: input.sourceType,
      title: input.title,
      text: input.text,
      external_id: input.externalId,
      uri: input.uri,
    });
    return {
      documentId: body.document_id,
      title: body.title,
      chunksCreated: body.chunks_created,
      skippedUnchanged: body.skipped_unchanged,
    };
  },

  async search(input: KnowledgeSearchInput): Promise<KnowledgeSearchHit[]> {
    const body = await apiClient.post<KnowledgeSearchHitBody[]>("/ai/knowledge/search", {
      organization_id: input.organizationId,
      query: input.query,
      top_k: input.topK,
      strategy: input.strategy,
      source_types: input.sourceTypes,
    });
    return body.map(toSearchHit);
  },
};
