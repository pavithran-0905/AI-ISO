# Error Handling

## Three distinct error types from the API client

`api/client.ts` throws one of three types, never a bare `Error`, so a
caller can react precisely:

- `ApiRequestError` — the backend responded with a real error envelope
  (`{success: false, message, error: {code, details}}`) or a non-2xx
  status. Carries `status`, `code`, `details`.
- `ApiTimeoutError` — the request was aborted by the client's own
  timeout (default 30s) before the backend responded at all.
- `ApiNetworkError` — `fetch` itself failed (offline, DNS, connection
  refused) — the request never reached the backend.

## The reusable states components render for them

All in `components/feedback/`, per Prompt 001 §19:

| State | Component | When |
|---|---|---|
| Loading | `LoadingState` | An in-flight query/mutation with nothing to show yet. |
| Skeleton | `Skeleton` | A loading placeholder shaped like the eventual content. |
| Empty | `EmptyState` | A successful response with zero items — nothing went wrong. |
| Error | `ErrorState` (optional `onRetry`) | An `ApiRequestError`, or any other unexpected failure. |
| Unauthorized / Forbidden | `AccessDeniedState` (`variant`) | A 401/403, or the route-level equivalents at `/unauthorized` and `/forbidden`. |
| Offline | `OfflineState` (optional `onRetry`) | Specifically an `ApiNetworkError`. |
| Partial data | `PartialDataNotice` | A response with *some* usable data alongside a partial failure. |
| Success | *(no dedicated component)* | The feature's real content — see below. |
| Retry | *(folded into `ErrorState`/`OfflineState`)* | The `onRetry` prop on either. |

"Success" has no dedicated wrapper component: rendering a feature's
real content *is* the success state. A component that exists only to
say "things worked, here's your data" would be pure ceremony around
whatever the feature was already going to render.

## React error boundaries

`app/error.tsx` (segment-level, nested inside the root layout) and
`app/global-error.tsx` (replaces the root layout entirely if it itself
throws — the only one that renders its own `<html>`/`<body>`) both
render `ErrorState` with the boundary's own `reset()` as `onRetry`.
Both currently just `console.error` the caught error — wiring to a real
error-reporting service is a later prompt's concern, not invented here.
