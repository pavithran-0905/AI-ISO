import { Check, TriangleAlert } from "lucide-react";

import { cn } from "@/utils/cn";

export interface WizardStep {
  id: string;
  label: string;
  /** Set once a step has been visited/submitted — an `"invalid"` step
   * renders an error indicator instead of its check/number so a user
   * can see which step needs attention without leaving the current
   * one. Omit (or `"pending"`) for a step with no validation result
   * yet. */
  status?: "pending" | "invalid";
}

/**
 * Wizard Layout (docs/frontend Prompt 001 §16, standardized by Prompt
 * 003 §31) — a step indicator plus content area plus footer action
 * slot, for future multi-step flows (e.g. onboarding, guided
 * remediation). Previous/next, save/cancel, and a final confirmation
 * screen are all just ordinary steps rendered through `children` and
 * `footer` — this component owns only the indicator and the frame, not
 * any flow-specific behavior.
 */
export function WizardLayout({
  steps,
  currentStepId,
  children,
  footer,
}: {
  steps: WizardStep[];
  currentStepId: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  const currentIndex = steps.findIndex((step) => step.id === currentStepId);

  return (
    <div className="bg-background text-foreground flex min-h-screen flex-col">
      <ol className="border-border flex items-center gap-4 border-b px-6 py-4" aria-label="Progress">
        {steps.map((step, index) => {
          const isComplete = index < currentIndex;
          const isCurrent = step.id === currentStepId;
          const isInvalid = step.status === "invalid";
          return (
            <li key={step.id} className="flex items-center gap-2">
              <span
                aria-current={isCurrent ? "step" : undefined}
                className={cn(
                  "flex size-6 items-center justify-center rounded-full text-xs font-medium",
                  isInvalid && "bg-danger text-danger-foreground",
                  !isInvalid && isComplete && "bg-primary text-primary-foreground",
                  !isInvalid && isCurrent && !isComplete && "border-primary text-primary border-2",
                  !isInvalid && !isCurrent && !isComplete && "bg-muted text-muted-foreground",
                )}
              >
                {isInvalid ? (
                  <TriangleAlert className="size-3.5" aria-hidden="true" />
                ) : isComplete ? (
                  <Check className="size-3.5" aria-hidden="true" />
                ) : (
                  index + 1
                )}
              </span>
              <span
                className={cn(
                  "text-sm",
                  isInvalid ? "text-danger font-medium" : isCurrent ? "font-medium" : "text-muted-foreground",
                )}
              >
                {step.label}
                {isInvalid && <span className="sr-only"> (needs attention)</span>}
              </span>
            </li>
          );
        })}
      </ol>
      <div className="flex-1 overflow-auto p-6">{children}</div>
      <div className="border-border flex items-center justify-end gap-2 border-t px-6 py-4">
        {footer}
      </div>
    </div>
  );
}
