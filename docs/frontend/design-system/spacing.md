# Spacing

Tailwind CSS v4's own default spacing scale (a fixed rem-based
progression: `1 = 0.25rem`) is used as-is — not re-invented, per the
comment already in `app/globals.css` explaining why (docs/010 names no
enterprise-specific override, and Tailwind's scale is already
semantic, not arbitrary). §8 asks that *usage* be documented, not that
a new scale be invented — this document is that usage guide.

## Where each level applies

| Context | Value | Rationale |
|---|---|---|
| Page padding | `p-6` | Matches `layouts/main-layout.tsx`'s existing `<main>` padding. |
| Section spacing (between major blocks on a page) | `gap-6` | Matches the dashboard placeholder's own `flex flex-col gap-6`. |
| Card padding | `p-4` (header/content), `pt-0` on content directly under a header | Matches `Card`'s existing `CardHeader`/`CardContent`. |
| Table cells | `px-3 py-2` at default density, `px-2 py-1` at compact density | See `tables.md`. |
| Form fields | `gap-1.5` between label/control/description within one `FormField`; `gap-4` between fields in a form | Matches `FormField`'s own implementation. |
| Toolbars / FilterBar | `gap-2` between controls, `p-3` container padding | Matches `Popover`'s panel padding. |
| Dialogs | `p-4` per section (header/body/footer), separated by `border-border` | Matches `Dialog`'s own implementation. |
| Drawers | Same as Dialog — `p-4` per section. | Matches `Drawer`'s own implementation. |
| Navigation items | `px-3 py-2` (matches `Tabs`) | Kept identical to `Tabs` so nav and tabs read as the same visual family. |
| Dashboards | `gap-4` between cards, `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` | Matches the existing dashboard placeholder's own grid. |

## Rule

A component picks one of the values above for its context — never an
arbitrary `p-[13px]`. If a genuinely new context needs a value not
listed here, add it to this table when the component ships, with the
same one-line rationale style.
