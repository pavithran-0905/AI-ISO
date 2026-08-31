import { useEffect, useState } from "react";

/**
 * A small, shared debounce (§31: "Recommended debounce: 150–300ms").
 * Promoted here once a third consumer (Global Search, Prompt 017)
 * needed the same local-`useEffect`+`setTimeout` pattern already used
 * ad hoc in `features/infrastructure/components/topology-search.tsx`
 * and `features/audit/components/audit-filters.tsx`.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
