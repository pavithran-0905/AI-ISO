# Forms

Every rule below is implemented, not aspirational — `FormField`
(`components/forms/form-field.tsx`) is the one composition point that
enforces them, so a feature using it gets them for free.

## Labels

Every field has a real `<label>` (`Label`, wired via `htmlFor`/`id`
inside `FormField`) — never placeholder text as the only label (§14
forbids it explicitly, and it fails a screen reader the moment the
field is focused and the placeholder's implied "label" scrolls out of
relevance).

## Required / optional

`FormField`'s `required` prop drives three things at once: a visible
`*` next to the label (danger-toned, `aria-hidden` since the
`aria-required` on the control already announces it to a screen
reader), the *absence* of a visible "Optional" tag, and
`aria-required` on the control itself. A field that doesn't pass
`required` shows "Optional" explicitly — §14 requires distinguishing
both directions, not just marking required fields.

## Descriptions and errors

`FormField`'s `description` renders as `caption`-styled helper text;
`error` (when present) replaces it and renders `role="alert"` in
`danger` tone. Both are wired into the control's `aria-describedby`
automatically — a screen reader announces the field's purpose and
(once one exists) its current error together.

## Disabled / loading submission / success / server errors

- **Disabled fields**: every form control (`Input`/`Textarea`/`Select`/
  `Checkbox`/`Radio`/`Switch`) has a `disabled:opacity-50
  disabled:pointer-events-none` treatment — consistent across all six.
- **Loading submission**: the submitting `Button` sets `loading` (its
  existing prop from Prompt 001) — no separate form-level spinner
  pattern; the action that's pending is the one thing that should show it.
- **Success**: `toast.success(...)` for a completed submission — not a
  page-level `Alert`, since a successful submission is a transient
  confirmation, not a persistent condition of the page (see
  `component-guidelines.md`'s Alert-vs-Toast rule).
- **Server errors**: a form-level `Alert` (`tone="danger"`) above the
  fields for an error that isn't attributable to one field (e.g. a
  409 conflict); a field-level `FormField error` for one that is.

## Keyboard navigation

Native elements throughout (`<input>`, `<textarea>`, `<select>`,
checkbox/radio `<input>`s) — Tab order, Space/Enter activation, and
arrow-key radio-group navigation all come from the platform, not
reimplemented.

## Not yet built

Client-side validation wiring (React Hook Form + Zod, both already
dependencies per Prompt 001, unused so far — see
`docs/frontend/architecture/frontend-architecture.md`) — no form
exists yet to wire them into. When one does, it should call
`FormField`'s `error` from the resolver's own field errors, not
duplicate error-display logic.
