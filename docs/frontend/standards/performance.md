# Performance

## In place today

- **Route-level code splitting** comes from Next.js App Router itself —
  every `page.tsx` is its own chunk by default; nothing extra to
  configure.
- **TanStack Query caching**: `staleTime: 30_000` by default
  (`providers/query-provider.tsx`), `staleTime: 5 * 60_000` specifically
  for the auth profile query (`auth/session.tsx`) — a user's own profile
  changes far less often than arbitrary feature data, so it's cached
  longer deliberately, not by accident.
- **`refetchOnWindowFocus: false`** — an enterprise operator switching
  tabs constantly shouldn't cause a refetch storm; features that
  genuinely need near-real-time data opt into their own shorter
  `staleTime`/polling rather than the global default assuming it for
  everyone.
- **The API client's own retry/timeout** (`api-architecture.md`) fails
  fast on a hung request (30s default) instead of leaving a query
  pending indefinitely.

## Deliberately not done yet

- **Virtualization** for large datasets — no list/table primitive exists
  yet to virtualize (Prompt 001 §34: no business screens in this
  prompt). Added when the first feature actually renders a large
  collection, not preemptively.
- **Memoization** — none of the components built in this prompt
  memoize (`useMemo`/`React.memo`), since none of them re-render
  expensively enough to justify it yet. Prompt 001 §22 is explicit:
  "Do not introduce premature optimization. Measure before adding
  complex optimization." `permissions/hooks.ts`'s `usePermissions`
  does use `useMemo` — justified there because it returns a fresh object
  literal every render otherwise, which would break any consumer that
  depends on it in a `useEffect` dependency array.
- **Bundle analysis** — not run in this prompt; nothing has shipped that
  would meaningfully move the needle yet (no charting library, no rich
  text editor, no large icon set beyond the already-used `lucide-react`).
- **Image optimization** — no images are used in the app yet
  (`public/` only has `robots.txt`); Next's own `<Image>` is the
  established path once one is needed.
