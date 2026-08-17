"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { resolveTheme, useThemeStore } from "@/state/theme-store";

function subscribeNoop() {
  return () => {};
}

/** `resolveTheme("system")` reads `window.matchMedia`, unavailable
 * during SSR — `useSyncExternalStore` (not a `useEffect` + `setState`
 * "mounted" flag, which trips `react-hooks/set-state-in-effect`) is
 * the platform-sanctioned way to render a server-safe value on first
 * render and the real client value immediately after hydration. */
function useIsClient(): boolean {
  return useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false,
  );
}

export function ThemeToggle() {
  const theme = useThemeStore((state) => state.theme);
  const setTheme = useThemeStore((state) => state.setTheme);
  const isClient = useIsClient();

  const resolved = isClient ? resolveTheme(theme) : "light";

  return (
    <Button
      variant="ghost"
      aria-label="Toggle theme"
      onClick={() => setTheme(resolved === "dark" ? "light" : "dark")}
    >
      {resolved === "dark" ? (
        <Sun className="size-4" aria-hidden="true" />
      ) : (
        <Moon className="size-4" aria-hidden="true" />
      )}
    </Button>
  );
}
