"use client";

import { HelpCircle, Menu, Search } from "lucide-react";

import { env } from "@/config/env";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { IconButton } from "@/components/ui/icon-button";
import { NotificationArea } from "@/components/navigation/notification-area";
import { UserMenu } from "@/components/navigation/user-menu";
import { useCommandPaletteStore } from "@/state/command-palette-store";
import { useMobileNavStore } from "@/state/mobile-nav-store";

const HELP_URL = "https://github.com/pavicsi52-commits/AI-ISO";

/**
 * The global header (docs/frontend Prompt 003 §6). Deliberately not
 * overloaded (§6: "keep high-frequency actions immediately
 * accessible"): identity, an environment indicator (only when not
 * production — a badge that's always visible would just be noise in
 * the one environment where it doesn't matter), the search/command
 * palette trigger (one button — `@/components/navigation/command-palette.tsx`
 * serves both §15 and §16, see its own module docstring for why),
 * notifications, help, and the account menu.
 */
export function Header() {
  const showCommandPalette = useCommandPaletteStore((state) => state.show);
  const toggleMobileNav = useMobileNavStore((state) => state.toggle);

  return (
    <header className="border-border flex h-14 items-center justify-between gap-4 border-b px-6">
      <div className="flex items-center gap-3">
        <IconButton
          icon={Menu}
          aria-label="Toggle navigation"
          variant="ghost"
          className="md:hidden"
          onClick={toggleMobileNav}
        />
        <span className="text-sm font-semibold tracking-tight">AI-IOS</span>
        {env.appEnv !== "production" && (
          <Badge variant="outline" className="uppercase">
            {env.appEnv}
          </Badge>
        )}
      </div>

      <button
        type="button"
        onClick={showCommandPalette}
        className="text-muted-foreground hover:border-muted-foreground/50 border-border bg-input flex h-8 w-full max-w-sm items-center gap-2 rounded-md border px-3 text-sm transition-colors"
      >
        <Search className="size-4" aria-hidden="true" />
        <span className="flex-1 text-left">Search pages and commands…</span>
        <kbd className="border-border bg-surface rounded border px-1.5 py-0.5 font-mono text-[10px]">⌘K</kbd>
      </button>

      <div className="flex items-center gap-1">
        <IconButton
          icon={HelpCircle}
          aria-label="Documentation"
          variant="ghost"
          onClick={() => window.open(HELP_URL, "_blank", "noopener")}
        />
        <NotificationArea />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
