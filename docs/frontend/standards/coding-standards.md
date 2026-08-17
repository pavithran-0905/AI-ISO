# Coding Standards

- **Strict TypeScript.** `tsconfig.json` has `strict: true`. Avoid `any`;
  when a third-party type is genuinely unknown, use `unknown` and narrow
  it. No unnecessary `@ts-ignore` — if one is unavoidable, it needs a
  comment explaining why (see `TokenClaims` handling in `auth/jwt.ts`
  for the pattern: explain the *constraint*, not the mechanics).
- **ESLint + Prettier** (`eslint.config.mjs`, `prettier.config.mjs`,
  `prettier-plugin-tailwindcss` for class-order sorting) gate every
  commit's formatting and catch dead code / unused imports /
  React-hooks correctness (see the real bug this caught in
  `layouts/split-pane-layout.tsx` during this prompt's own build — a
  callback referencing itself before declaration).
- **No dead code, no unused dependencies.** Before adding a package,
  check whether the capability already exists (Prompt 001 §4) — e.g.
  `utils/cn.ts` is a ~15-line in-house class-joiner instead of a `clsx`
  dependency.
- **No duplicated business logic.** A second near-identical component
  is a sign the first one needed a parameter, not a copy —
  `components/feedback/access-denied-state.tsx`'s single
  `variant: "unauthorized" | "forbidden"` component instead of two
  near-identical ones is the concrete example in this codebase.
- **No magic constants without explanation.** Every timing/retry/limit
  constant in `api/client.ts` (`DEFAULT_TIMEOUT_MS`, `MAX_RETRIES`,
  `RETRY_BASE_DELAY_MS`) is named and adjacent to the code that uses it.
- **Comments explain the non-obvious**, not what the code already says.
  A comment earns its place by capturing a constraint that isn't visible
  in the code itself — a backend gap (`auth/types.ts`), a Next.js
  convention that would otherwise be surprising (`app/error.tsx` vs.
  `app/global-error.tsx`), a deliberate trade-off (localStorage token
  storage in `auth/store.ts`).
