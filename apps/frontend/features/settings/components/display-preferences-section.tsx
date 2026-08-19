"use client";

import { AlignJustify, Moon, Rows3, Sun, SunMoon } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Label } from "@/components/forms/label";
import { IconButton } from "@/components/ui/icon-button";
import { useThemeStore, type Theme } from "@/state/theme-store";
import { useTableDensityStore } from "@/state/table-density-store";

const THEME_OPTIONS: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: SunMoon },
];

/**
 * Display preferences — deliberately backed by the *existing* local,
 * per-device `useThemeStore`/`useTableDensityStore` (Prompts 002/006),
 * not `/users/preferences.theme` (a real backend field, confirmed to
 * exist, that this frontend intentionally leaves unsynced). §17
 * explicitly forbids a second theme system; wiring a backend-synced
 * copy on top of an already-working, already-used-everywhere local
 * mechanism would be exactly that, and risks the two silently
 * disagreeing about what's actually applied. See the developer guide's
 * "Why theme stays local" section.
 */
export function DisplayPreferencesSection() {
  const theme = useThemeStore((state) => state.theme);
  const setTheme = useThemeStore((state) => state.setTheme);
  const density = useTableDensityStore((state) => state.density);
  const setDensity = useTableDensityStore((state) => state.setDensity);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Display</CardTitle>
        <CardDescription>Applies immediately, on this device only.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label>Theme</Label>
          <div className="flex items-center gap-1" role="group" aria-label="Theme">
            {THEME_OPTIONS.map((option) => (
              <IconButton
                key={option.value}
                icon={option.icon}
                aria-label={option.label}
                aria-pressed={theme === option.value}
                variant={theme === option.value ? "secondary" : "outline"}
                onClick={() => setTheme(option.value)}
              />
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Table density</Label>
          <div className="flex items-center gap-1" role="group" aria-label="Table density">
            <IconButton
              icon={Rows3}
              aria-label="Comfortable density"
              aria-pressed={density === "comfortable"}
              variant={density === "comfortable" ? "secondary" : "outline"}
              onClick={() => setDensity("comfortable")}
            />
            <IconButton
              icon={AlignJustify}
              aria-label="Compact density"
              aria-pressed={density === "compact"}
              variant={density === "compact" ? "secondary" : "outline"}
              onClick={() => setDensity("compact")}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
