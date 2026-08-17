/**
 * Icon rules (docs/frontend Prompt 002 §11). `lucide-react` only — no
 * second icon library, no emoji-as-UI-icon (§11 forbids both
 * explicitly). This module is the one place icon *sizing* is decided;
 * a component picks a size class from here, never an arbitrary
 * `size-[17px]`.
 */

/** Tailwind `size-*` utility classes, indexed by usage context. Use the
 * narrowest one that fits — a nav icon should never reach for
 * `action` sized just because it's convenient. */
export const iconSize = {
  /** Inline with `bodySmall`/`caption` text — status dots, inline hints. */
  inline: "size-3",
  /** Inline with `body` text, inside a `Badge`/`StatusBadge`, a table cell action. */
  action: "size-4",
  /** A standalone `IconButton`, a nav item's own icon. */
  control: "size-5",
  /** A section/page-level illustrative icon — `EmptyState`, `ErrorState`. */
  feature: "size-8",
} as const;

export type IconSizeToken = keyof typeof iconSize;

/** The gap between an icon and its adjacent label — one value so
 * `Button`, nav items, and status displays never drift apart. */
export const iconLabelGapClass = "gap-2";

/**
 * Icon-to-usage rules, as documentation (not enforceable at the type
 * level, since Lucide doesn't tag icons by intended use):
 *
 * - Status icons come from `@/lib/status`'s `STATUS_TAXONOMY` only —
 *   never picked ad hoc for a status display.
 * - Action icons (Edit, Trash2, Download, ...) sit at `iconSize.action`
 *   inside a `Button`/`IconButton`, always paired with an accessible
 *   name (visible label, or `aria-label` on an icon-only `IconButton`).
 * - Destructive action icons (Trash2, XCircle, AlertOctagon) pair with
 *   the `danger` tone/variant wherever they appear — never a bare icon
 *   with no color signal for a destructive action.
 * - Navigation icons sit at `iconSize.control`, left of the label, one
 *   icon per nav item — a nav item is never icon-only at desktop width.
 */
