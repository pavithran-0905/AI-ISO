import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * A `QueryClientProvider` wired for tests: retries disabled so a test
 * hitting a failing query fails fast instead of waiting out backoff.
 * Used by any test exercising a hook that calls `useQuery`/`useMutation`
 * (`useSession` and anything built on it).
 */
export function TestQueryProvider({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
