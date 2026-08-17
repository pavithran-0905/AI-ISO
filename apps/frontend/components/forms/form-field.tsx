import { useId } from "react";

import { Label } from "@/components/forms/label";

export interface FormFieldProps {
  label: string;
  /** Omit for an optional field — §14 requires distinguishing
   * required/optional; an asterisk on `label` alone isn't enough for a
   * screen reader, so this also sets `aria-required`. */
  required?: boolean;
  description?: string;
  error?: string;
  /** Receives `{ id, "aria-describedby", "aria-invalid", "aria-required" }` — spread
   * these onto the actual `Input`/`Textarea`/`Select`. */
  children: (fieldProps: {
    id: string;
    "aria-describedby": string | undefined;
    "aria-invalid": boolean | undefined;
    "aria-required": boolean | undefined;
  }) => React.ReactNode;
}

/**
 * The label/description/error composition every form control uses
 * (§14) — wires `aria-describedby` to whichever of description/error
 * is present so a screen reader announces both the field's purpose and
 * its current error, not just its label.
 */
export function FormField({ label, required = false, description, error, children }: FormFieldProps) {
  const id = useId();
  const descriptionId = description ? `${id}-description` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <Label htmlFor={id}>
          {label}
          {required && (
            <span className="text-danger ml-0.5" aria-hidden="true">
              *
            </span>
          )}
        </Label>
        {!required && <span className="text-muted-foreground text-xs">Optional</span>}
      </div>
      {children({
        id,
        "aria-describedby": describedBy,
        "aria-invalid": error ? true : undefined,
        "aria-required": required || undefined,
      })}
      {description && !error && (
        <p id={descriptionId} className="text-muted-foreground text-xs">
          {description}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-danger text-xs">
          {error}
        </p>
      )}
    </div>
  );
}
