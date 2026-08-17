/**
 * The typography scale (docs/frontend Prompt 002 §7). Every text style
 * in the app should come from here rather than an ad hoc `text-*
 * font-*` combination picked per component — that's exactly the kind
 * of drift a design system exists to prevent.
 *
 * Values, not components: a `className` string composes into whatever
 * element is semantically correct for its context (`cn(typography.pageTitle, "truncate")`
 * on an `<h1>` here, an `<h2>` there) without this module making that
 * choice for the caller.
 */

export const typography = {
  /** The largest text in the app — a hero/marketing-adjacent moment.
   * Rare; most enterprise screens never need this. */
  display: "text-3xl font-semibold tracking-tight text-balance",
  /** A route's own `<h1>` — one per page. */
  pageTitle: "text-xl font-semibold tracking-tight",
  /** A section heading within a page. */
  sectionTitle: "text-base font-semibold tracking-tight",
  /** A card's own heading — matches `CardTitle`. */
  cardTitle: "text-sm font-semibold",
  /** Default body copy. */
  body: "text-sm leading-relaxed",
  /** Secondary/supporting copy — never the only carrier of critical information. */
  bodySmall: "text-xs leading-relaxed",
  /** A form field's label, or a small all-context label (not the `Label` component's own default styling, which composes this). */
  label: "text-xs font-medium",
  /** Muted, de-emphasized text — timestamps, helper text, metadata. */
  caption: "text-xs text-muted-foreground",
  /** Inline or block code, IDs, hashes — anything that must not
   * ligature or proportionally reflow. */
  code: "font-mono text-xs",
  /** A KPI/metric's own headline number. Tabular figures so a column of
   * metrics aligns even as digits change. */
  metric: "text-2xl font-semibold tracking-tight tabular-nums",
  /** Table cell text — deliberately the same size as `body` but named
   * separately so a future density change can retune it independently. */
  tableText: "text-sm",
} as const;

export type TypographyToken = keyof typeof typography;

/** Truncate to one line with an ellipsis — the default for any cell or
 * label that must not wrap and push a layout around. */
export const truncateClass = "truncate";

/** Allow wrapping but avoid a orphaned single word on its own line —
 * for body copy and descriptions, never for table cells or labels. */
export const wrapBalancedClass = "text-pretty";
