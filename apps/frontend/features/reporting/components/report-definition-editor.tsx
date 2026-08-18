"use client";

import { GripVertical, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Card, CardContent } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { SectionFormDialog } from "@/features/reporting/components/section-form-dialog";
import type { ReportDefinition, ReportSection } from "@/features/reporting/types";

/**
 * The designer document editor (§7) — a real, structured, schema-driven
 * section list (add/edit/remove/reorder), not a drag-and-drop canvas
 * the backend contract has no concept of. Each section's own fields are
 * edited through `SectionFormDialog`, matching the real per-kind
 * requirements the backend validates on write. There is no live chart/
 * table preview: rendering happens server-side only (§10 — preview
 * means viewing a generated export, not recreating the renderer in the
 * browser).
 */
export function ReportDefinitionEditor({
  definition,
  onChange,
}: {
  definition: ReportDefinition;
  onChange: (definition: ReportDefinition) => void;
}) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [addingNew, setAddingNew] = useState(false);

  function updateSection(index: number, section: ReportSection) {
    onChange({ ...definition, sections: definition.sections.map((existing, i) => (i === index ? section : existing)) });
  }

  function addSection(section: ReportSection) {
    onChange({ ...definition, sections: [...definition.sections, section] });
  }

  function removeSection(index: number) {
    onChange({ ...definition, sections: definition.sections.filter((_, i) => i !== index) });
  }

  function moveSection(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= definition.sections.length) return;
    const next = [...definition.sections];
    [next[index], next[target]] = [next[target], next[index]];
    onChange({ ...definition, sections: next });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="definition-title">Title</Label>
          <Input id="definition-title" value={definition.title} onChange={(event) => onChange({ ...definition, title: event.target.value })} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="definition-subtitle">Subtitle</Label>
          <Input id="definition-subtitle" value={definition.subtitle ?? ""} onChange={(event) => onChange({ ...definition, subtitle: event.target.value })} />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium">Sections</p>
        {definition.sections.length === 0 && <p className="text-muted-foreground text-sm">No sections yet — add one below.</p>}
        {definition.sections.map((section, index) => (
          <Card key={section.key || index}>
            <CardContent className="flex items-center justify-between gap-3 p-3">
              <div className="flex items-center gap-2">
                <GripVertical className="text-muted-foreground size-4" aria-hidden="true" />
                <div>
                  <p className="text-sm font-medium">{section.title || section.key || "Untitled section"}</p>
                  <p className="text-muted-foreground text-xs">{section.kind.replace("_", " ")}</p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <IconButton icon={Pencil} aria-label="Edit section" variant="ghost" onClick={() => setEditingIndex(index)} />
                <Button variant="ghost" onClick={() => moveSection(index, -1)} disabled={index === 0}>
                  ↑
                </Button>
                <Button variant="ghost" onClick={() => moveSection(index, 1)} disabled={index === definition.sections.length - 1}>
                  ↓
                </Button>
                <IconButton icon={Trash2} aria-label="Remove section" variant="ghost" onClick={() => removeSection(index)} />
              </div>
            </CardContent>
          </Card>
        ))}
        <Button variant="outline" onClick={() => setAddingNew(true)} className="w-fit gap-1.5">
          <Plus className="size-4" aria-hidden="true" />
          Add section
        </Button>
      </div>

      {editingIndex !== null && (
        <SectionFormDialog
          key={definition.sections[editingIndex]?.key}
          section={definition.sections[editingIndex] ?? null}
          open={editingIndex !== null}
          onClose={() => setEditingIndex(null)}
          onSave={(section) => updateSection(editingIndex, section)}
        />
      )}

      {addingNew && (
        <SectionFormDialog key="new-section" section={null} open={addingNew} onClose={() => setAddingNew(false)} onSave={addSection} />
      )}
    </div>
  );
}
