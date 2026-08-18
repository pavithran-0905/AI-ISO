"use client";

import { Card, CardContent } from "@/components/data-display/card";
import type { ReportDefinition } from "@/features/reporting/types";

/** A read-only view of a template version's designer document — the
 * same section list the editor manages, without edit controls. There
 * is no live preview to render alongside it: sections are rendered
 * server-side only (see `GenerationResult`'s own docstring). */
export function DefinitionSummary({ definition }: { definition: ReportDefinition }) {
  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="text-sm font-medium">{definition.title}</p>
        {definition.subtitle && <p className="text-muted-foreground text-xs">{definition.subtitle}</p>}
      </div>
      {definition.sections.length === 0 ? (
        <p className="text-muted-foreground text-sm">No sections.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {definition.sections.map((section) => (
            <li key={section.key}>
              <Card>
                <CardContent className="flex items-center justify-between gap-3 p-3">
                  <p className="text-sm font-medium">{section.title || section.key}</p>
                  <p className="text-muted-foreground text-xs">{section.kind.replace("_", " ")}</p>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
