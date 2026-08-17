import { typography } from "@/lib/typography";
import { cn } from "@/utils/cn";

export interface PageHeaderProps {
  /** Small context label above the title (e.g. a parent section name) —
   * optional, omit when the title alone is unambiguous. */
  eyebrow?: string;
  title: string;
  description?: string;
  /** A `StatusIndicator`/`StatusBadge`, rendered next to the title. */
  status?: React.ReactNode;
  /** At most one — docs/frontend Prompt 003 §14: "one clear primary
   * action where appropriate." A second "primary-looking" button is a
   * design smell this type doesn't prevent, but the prop being
   * singular (not an array) nudges toward it. */
  primaryAction?: React.ReactNode;
  /** Secondary actions, rendered before the primary action (reading
   * order: secondary, then primary, matching the visual weight
   * progression left-to-right). */
  secondaryActions?: React.ReactNode;
  /** Overflow actions (e.g. a `Dropdown` for less-common actions) —
   * rendered last. */
  overflowActions?: React.ReactNode;
  className?: string;
}

/**
 * The reusable page-header framework (docs/frontend Prompt 003 §13) —
 * every future feature page's own title/actions area, not a
 * feature-specific component. Breadcrumbs are rendered separately
 * (`Breadcrumbs`, above the shell's page-header slot) rather than by
 * this component, since they're a shell-level concern shared across
 * every page, not part of any one page's own header.
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  status,
  primaryAction,
  secondaryActions,
  overflowActions,
  className,
}: PageHeaderProps) {
  const hasActions = primaryAction || secondaryActions || overflowActions;

  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-4", className)}>
      <div className="flex flex-col gap-1">
        {eyebrow && <span className={cn(typography.caption, "uppercase tracking-wide")}>{eyebrow}</span>}
        <div className="flex items-center gap-2">
          <h1 className={typography.pageTitle}>{title}</h1>
          {status}
        </div>
        {description && <p className={cn(typography.body, "text-muted-foreground")}>{description}</p>}
      </div>
      {hasActions && (
        <div className="flex items-center gap-2">
          {secondaryActions}
          {primaryAction}
          {overflowActions}
        </div>
      )}
    </div>
  );
}
