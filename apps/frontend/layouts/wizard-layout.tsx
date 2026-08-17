import { Check } from "lucide-react";

import { cn } from "@/utils/cn";

export interface WizardStep {
  id: string;
  label: string;
}

/**
 * Wizard Layout (docs/frontend Prompt 001 §16) — a step indicator plus
 * content area plus footer action slot, for future multi-step flows
 * (e.g. onboarding, guided remediation).
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
          return (
            <li key={step.id} className="flex items-center gap-2">
              <span
                aria-current={isCurrent ? "step" : undefined}
                className={cn(
                  "flex size-6 items-center justify-center rounded-full text-xs font-medium",
                  isComplete && "bg-primary text-primary-foreground",
                  isCurrent && !isComplete && "border-primary text-primary border-2",
                  !isCurrent && !isComplete && "bg-muted text-muted-foreground",
                )}
              >
                {isComplete ? <Check className="size-3.5" aria-hidden="true" /> : index + 1}
              </span>
              <span
                className={cn("text-sm", isCurrent ? "font-medium" : "text-muted-foreground")}
              >
                {step.label}
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
