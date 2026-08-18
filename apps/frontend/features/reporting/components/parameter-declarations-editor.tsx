"use client";

import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/forms/checkbox";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { PARAMETER_KINDS, type ParameterDeclaration, type ParameterKindValue } from "@/features/reporting/types";

/** What a template declares (§8's "PARAMETERS") — a caller of
 * `POST /reports/generate` can only bind values these keys allow, so
 * this is where a template author defines that contract. Replaced
 * wholesale on every version (`_replace_parameters()`), never merged —
 * removing a row here genuinely removes that parameter from the new
 * version. */
export function ParameterDeclarationsEditor({
  parameters,
  onChange,
}: {
  parameters: ParameterDeclaration[];
  onChange: (parameters: ParameterDeclaration[]) => void;
}) {
  function update(index: number, patch: Partial<ParameterDeclaration>) {
    onChange(parameters.map((param, i) => (i === index ? { ...param, ...patch } : param)));
  }

  function remove(index: number) {
    onChange(parameters.filter((_, i) => i !== index));
  }

  function add() {
    onChange([
      ...parameters,
      { key: "", label: "", kind: "string", required: false, allowedValues: [], displayOrder: parameters.length },
    ]);
  }

  return (
    <div className="flex flex-col gap-3">
      {parameters.map((param, index) => (
        <div key={index} className="border-border flex flex-wrap items-end gap-2 rounded-md border p-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`param-key-${index}`}>Key</Label>
            <Input id={`param-key-${index}`} value={param.key} onChange={(event) => update(index, { key: event.target.value })} className="w-32" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`param-label-${index}`}>Label</Label>
            <Input id={`param-label-${index}`} value={param.label} onChange={(event) => update(index, { label: event.target.value })} className="w-40" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`param-kind-${index}`}>Kind</Label>
            <Select id={`param-kind-${index}`} value={param.kind} onChange={(event) => update(index, { kind: event.target.value as ParameterKindValue })} className="w-32">
              {PARAMETER_KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {kind}
                </option>
              ))}
            </Select>
          </div>
          {param.kind === "enum" && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`param-allowed-${index}`}>Allowed values (comma-separated)</Label>
              <Input
                id={`param-allowed-${index}`}
                value={param.allowedValues.join(", ")}
                onChange={(event) => update(index, { allowedValues: event.target.value.split(",").map((v) => v.trim()).filter(Boolean) })}
                className="w-56"
              />
            </div>
          )}
          <label className="flex items-center gap-1.5 pb-2 text-sm">
            <Checkbox checked={param.required} onChange={(event) => update(index, { required: event.target.checked })} />
            Required
          </label>
          <IconButton icon={X} aria-label="Remove parameter" variant="ghost" onClick={() => remove(index)} />
        </div>
      ))}
      <Button variant="outline" onClick={add} className="w-fit gap-1.5">
        <Plus className="size-4" aria-hidden="true" />
        Add parameter
      </Button>
    </div>
  );
}
