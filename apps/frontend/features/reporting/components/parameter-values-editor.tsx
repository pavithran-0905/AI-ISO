"use client";

import { Checkbox } from "@/components/forms/checkbox";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import type { ParameterDeclaration } from "@/features/reporting/types";

/**
 * One input per parameter a template actually declares (§8: "only
 * expose supported fields") — the input type follows the parameter's
 * own `kind`, never a generic free-text box for everything. Shown only
 * once a template is selected; a report with no template has nothing
 * declared to bind values against.
 */
export function ParameterValuesEditor({
  parameters,
  values,
  onChange,
}: {
  parameters: ParameterDeclaration[];
  values: Record<string, unknown>;
  onChange: (values: Record<string, unknown>) => void;
}) {
  if (parameters.length === 0) return null;

  function setValue(key: string, value: unknown) {
    onChange({ ...values, [key]: value });
  }

  return (
    <div className="flex flex-col gap-4">
      {[...parameters]
        .sort((a, b) => a.displayOrder - b.displayOrder)
        .map((param) => {
          const inputId = `report-param-${param.key}`;
          const value = values[param.key] ?? param.defaultValue ?? "";

          return (
            <div key={param.key} className="flex flex-col gap-1.5">
              <Label htmlFor={inputId}>
                {param.label}
                {param.required && <span className="text-danger"> *</span>}
              </Label>
              {param.kind === "boolean" ? (
                <Checkbox id={inputId} checked={Boolean(value)} onChange={(event) => setValue(param.key, event.target.checked)} />
              ) : param.kind === "enum" ? (
                <Select id={inputId} value={String(value)} onChange={(event) => setValue(param.key, event.target.value)}>
                  <option value="">Select…</option>
                  {param.allowedValues.map((option) => (
                    <option key={String(option)} value={String(option)}>
                      {String(option)}
                    </option>
                  ))}
                </Select>
              ) : (
                <Input
                  id={inputId}
                  type={
                    param.kind === "integer" || param.kind === "number"
                      ? "number"
                      : param.kind === "date"
                        ? "date"
                        : param.kind === "datetime"
                          ? "datetime-local"
                          : "text"
                  }
                  value={String(value)}
                  onChange={(event) =>
                    setValue(param.key, param.kind === "integer" || param.kind === "number" ? event.target.valueAsNumber : event.target.value)
                  }
                />
              )}
              {param.description && <p className="text-muted-foreground text-xs">{param.description}</p>}
            </div>
          );
        })}
    </div>
  );
}
