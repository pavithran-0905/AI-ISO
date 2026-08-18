"use client";

import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";

export interface VariableEntry {
  key: string;
  value: string;
}

export function variablesToEntries(variables: Record<string, unknown>): VariableEntry[] {
  return Object.entries(variables).map(([key, value]) => ({ key, value: value === null || value === undefined ? "" : String(value) }));
}

export function entriesToVariables(entries: VariableEntry[]): Record<string, unknown> {
  return Object.fromEntries(entries.filter((entry) => entry.key.trim()).map((entry) => [entry.key.trim(), entry.value]));
}

/**
 * A free-form key/value editor — deliberately NOT a schema-driven,
 * per-type form (§13 asks for one "if automation parameters are
 * exposed by V1").
 *
 * They aren't. `automation-service` has a complete `AutomationParameter`
 * model, schema, service, and DI wiring — but **no routes**, so a
 * job's declared parameters can't be read. Its `parameter_type` isn't
 * even an enum (a plain `str(32)` with no validation), and there is no
 * `is_secret`, `allowed_values`, `min`/`max`, or `pattern` field
 * anywhere. The only real parameter surface is the untyped
 * `variables: dict[str, Any]` this editor targets. Building a typed,
 * validating form against a schema that cannot be fetched would be
 * exactly the invention §13's own "do not hardcode parameters"
 * instruction guards against. See
 * `docs/frontend/backend-v1-integration-limitations.md`.
 */
export function VariablesEditor({
  entries,
  onChange,
  label = "Variables",
  description,
}: {
  entries: VariableEntry[];
  onChange: (entries: VariableEntry[]) => void;
  label?: string;
  description?: string;
}) {
  function update(index: number, patch: Partial<VariableEntry>) {
    onChange(entries.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)));
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-0.5">
        <p className="text-sm font-medium">{label}</p>
        {description && <p className="text-muted-foreground text-xs">{description}</p>}
      </div>
      {entries.map((entry, index) => (
        <div key={index} className="flex items-end gap-2">
          <div className="flex flex-1 flex-col gap-1.5">
            {index === 0 && <Label htmlFor={`variable-key-${index}`}>Name</Label>}
            <Input id={`variable-key-${index}`} value={entry.key} onChange={(event) => update(index, { key: event.target.value })} />
          </div>
          <div className="flex flex-1 flex-col gap-1.5">
            {index === 0 && <Label htmlFor={`variable-value-${index}`}>Value</Label>}
            <Input id={`variable-value-${index}`} value={entry.value} onChange={(event) => update(index, { value: event.target.value })} />
          </div>
          <IconButton icon={X} aria-label="Remove variable" variant="ghost" onClick={() => onChange(entries.filter((_, i) => i !== index))} />
        </div>
      ))}
      <Button variant="outline" onClick={() => onChange([...entries, { key: "", value: "" }])} className="w-fit gap-1.5">
        <Plus className="size-4" aria-hidden="true" />
        Add variable
      </Button>
    </div>
  );
}
