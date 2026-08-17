# Testing

## Layers

- **Unit/component** — Vitest + Testing Library, `tests/unit/`,
  mirroring the source tree. 115 tests as of this prompt, covering every
  new module (`api/client.ts`'s auth/timeout/retry/cancellation
  behavior, `auth/`'s store/api/session/guards, `permissions/`'s
  capability model and guard components, every new layout, every new
  feedback state) plus the pre-existing dashboard/theme/provider tests.
- **Integration (seam) tests** — a small, deliberate category: e.g.
  `tests/unit/auth/session.test.tsx` doesn't just test `AuthBootstrap`
  in isolation, it mounts it, then calls the *real* `apiClient.get`
  and verifies the request actually carried the token the store held —
  proving the injection wiring (`dependency-boundaries.md`) works
  end-to-end, not just that each half compiles.
- **E2E** — Playwright, `tests/e2e/`. `dashboard.spec.ts`'s three specs
  (header renders, theme toggle works, live health data loads) predate
  this prompt; two pass without a running backend, the third
  legitimately requires the real gateway service up (it's testing real
  end-to-end connectivity, not something to mock away).
- **Accessibility** — enforced through the same Testing Library
  assertions (`getByRole`, landmark queries) rather than a separate
  axe-core pass in this prompt; see `accessibility.md` for what's
  verified.
- **Visual regression** — not established in this prompt. No Storybook
  yet (see `docs/frontend/README.md`), and no design surface complex
  enough yet to justify screenshot testing (Prompt 001 §22's "measure
  before adding" applies here too).

## What to test, concretely

Behavior, not implementation — every test added in this prompt asserts
on rendered output (`screen.getByRole`, `getByText`) or observable
state (`useAuthStore.getState()`), never on internal implementation
details like a component's own local variable names or the number of
times an internal helper was called for its own sake. The one exception
worth naming is `api/client.ts`'s tests, which do assert on `fetch`
call arguments (headers, method, body) — justified there because the
client's entire contract *is* what it sends over the wire.

## Mocking real backend calls

`vi.stubGlobal("fetch", ...)` at the test level (never a runtime mock
inside `api/client.ts` itself). Every mock response object must include
`ok` (`status >= 200 && status < 300`) — this prompt's own test suite
initially had this wrong in two pre-existing dashboard tests, which
silently worked under the old, simpler client (it only checked
`body.success`) and broke once the client started checking
`response.ok` too (a genuine correctness improvement, matching real
`fetch` behavior) — see `api-architecture.md`'s HTTP-status-handling row.
