import { cn } from "@/utils/cn";

/**
 * Fullscreen Workspace Layout (docs/frontend Prompt 001 §16) — no
 * navigation chrome, for immersive views (e.g. a future log viewer,
 * topology canvas, or terminal session) that need every pixel. An
 * optional minimal exit affordance is the caller's responsibility via
 * `topBar`, since what "exit" means is feature-specific.
 */
export function FullscreenLayout({
  children,
  topBar,
  className,
}: {
  children: React.ReactNode;
  topBar?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("bg-background text-foreground flex h-screen flex-col", className)}>
      {topBar}
      <div className="flex-1 overflow-hidden">{children}</div>
    </div>
  );
}
