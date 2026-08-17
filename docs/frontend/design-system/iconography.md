# Iconography

`lucide-react` only (§11) — already the established library since
Prompt 001's `ThemeToggle`. No second icon library, no emoji used as a
UI icon anywhere in the app.

## Sizes (`lib/icons.ts`)

| Token | Size | Use |
|---|---|---|
| `inline` | `size-3` | Inline with `bodySmall`/`caption` text — status dots, inline hints. |
| `action` | `size-4` | Inline with `body` text, inside `Badge`/`StatusBadge`, a table row action. |
| `control` | `size-5` | A standalone `IconButton`, a nav item's own icon. |
| `feature` | `size-8` | A section/page-level illustrative icon — `EmptyState`, `ErrorState`, `AccessDeniedState`, `OfflineState`. |

## Rules

- **Status icons** come from `@/lib/status`'s `STATUS_TAXONOMY` only —
  a feature never picks a status icon ad hoc. See `status-system.md`.
- **Action icons** (`Edit`, `Trash2`, `Download`, ...) sit at
  `iconSize.action` inside a `Button`/`IconButton`, always paired with
  an accessible name — a visible label, or `aria-label` on an
  icon-only `IconButton` (enforced at the type level: `IconButton`'s
  `aria-label` prop is required, not optional).
- **Destructive action icons** (`Trash2`, `XCircle`, `AlertOctagon`)
  pair with the `danger` tone/variant wherever they appear —
  `Dropdown`'s own `destructive` item flag does this automatically.
- **Navigation icons** sit at `iconSize.control`, left of the label,
  one per item — not yet built (no primary navigation exists yet, see
  `docs/frontend/architecture/routing.md`), documented here so the
  first implementation follows this rule from the start.
- **Icon + label gap**: `iconLabelGapClass` (`gap-2`) — one value so
  `Button`, nav items, and status displays never drift apart.
