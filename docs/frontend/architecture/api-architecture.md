# API Architecture

`apps/frontend/api/client.ts` is the only module in the app allowed to
call `fetch()`. Every feature must go through a feature-level API
function (e.g. `auth/api.ts`, `modules/dashboard/services/health-service.ts`)
that calls `apiClient.get/post/put/patch/delete`.

## What it does, per Prompt 001 §10's own checklist

| Requirement | Implementation |
|---|---|
| Base URL configuration | `@/config/env` (`NEXT_PUBLIC_API_BASE_URL`, defaulting to `http://localhost:8000`) — never hardcoded. |
| Authentication | Bearer token, injected via `setAuthTokenProvider` (see `dependency-boundaries.md`). `skipAuth` opts a call out (login, public health). |
| Request headers | `Accept`, `Content-Type` (when a body is present), `Authorization` (when authenticated). |
| Correlation/request IDs | `X-Request-ID` / `X-Correlation-ID`, both `crypto.randomUUID()`, matching the backend's own correlation-ID convention. |
| Timeout | `timeoutMs` (default 30s), via `AbortController`, combined with any caller-supplied `signal`. |
| Cancellation | Caller-supplied `AbortSignal` is combined with the internal timeout signal (`combineSignals`), so either can abort the request. |
| Response parsing | Unwraps the `{success, message, data, meta}` / `{success, message, error, meta}` envelope every AI-IOS backend service uses (see `types/api.ts`). A `204` returns `undefined` without attempting to parse a body. |
| Error normalization | `ApiRequestError` (a real backend error response), `ApiTimeoutError` (the request was aborted by the timeout), `ApiNetworkError` (`fetch` itself failed — offline, DNS, connection refused) — three distinct types so a caller can react differently (e.g. `OfflineState` specifically for `ApiNetworkError`). |
| Retry policy | GET/HEAD only, up to 2 retries with exponential backoff (300ms, 600ms), only on `502/503/504` or a network error. Never retries a mutation by default (`skipRetry` can also disable it for a GET with side-effect-sensitive semantics). |
| HTTP status handling | A `401` (when not `skipAuth`) calls `setUnauthorizedHandler`'s registered callback — the auth store clears the session, and any mounted `AuthGuard` redirects. |

## Why the client also retries, when TanStack Query already can

TanStack Query's own `retry` option (`providers/query-provider.tsx`,
`retry: 1`) governs whether a *query* re-runs after it has fully failed
— a coarser, cache-and-refetch-oriented retry. The client's retry is
scoped to a *single request attempt* recovering from a transient
502/503/504 or network blip before the caller (TanStack Query or
otherwise) ever sees a failure. They operate at different layers and
don't double up in practice: the client's retry either succeeds
(TanStack Query never sees a failure) or exhausts its 2 attempts and
throws once, which is what TanStack Query's own retry then evaluates.

## Backend contract

Every response envelope shape mirrors what the running backend actually
returns (confirmed via `services/api-gateway-service` and
`services/authentication-service` source, not assumed) — see
`types/api.ts` and `authentication.md`.
