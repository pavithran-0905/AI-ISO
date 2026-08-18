import { FileText } from "lucide-react";

import type { Citation } from "@/features/ai-assistant/types";

/** A message's or search hit's sources — `documentUri`/`uri` is
 * usually `null` (most ingested content has no external location), in
 * which case only the title is shown, never a dead/placeholder link. */
export function CitationsList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  return (
    <div className="border-border/60 mt-2 flex flex-col gap-1 border-t pt-2">
      <p className="text-muted-foreground text-xs font-medium">Sources</p>
      <ul className="flex flex-col gap-1">
        {citations.map((citation) => (
          <li key={citation.chunkId} className="flex items-center gap-1.5 text-xs">
            <FileText className="text-muted-foreground size-3 shrink-0" aria-hidden="true" />
            {citation.uri ? (
              <a href={citation.uri} target="_blank" rel="noreferrer" className="text-primary truncate hover:underline">
                {citation.title}
              </a>
            ) : (
              <span className="truncate">{citation.title}</span>
            )}
            <span className="text-muted-foreground shrink-0">({Math.round(citation.score * 100)}%)</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
