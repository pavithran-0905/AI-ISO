"use client";

import { CircleUserRound, HelpCircle, LogOut, Settings, Sparkles } from "lucide-react";
import { useState } from "react";

import { useSession } from "@/auth/session";
import { useLogout } from "@/auth/use-logout";
import { Dropdown } from "@/components/overlays/dropdown";
import { IconButton } from "@/components/ui/icon-button";
import { typography } from "@/lib/typography";

const HELP_URL = "https://github.com/pavicsi52-commits/AI-ISO";

/**
 * The user/account menu (docs/frontend Prompt 003 §18, logout wired by
 * Prompt 004 §11) — built on the real session (`@/auth/session`),
 * never inventing an attribute the backend doesn't confirm.
 * `role`/`organizationId` are frequently `null` today (the documented
 * backend gap — see `docs/frontend/architecture/authentication.md`);
 * this menu shows "Not assigned"/"No organization" rather than
 * guessing or omitting the row entirely, so the gap is visible, not
 * hidden.
 */
export function UserMenu() {
  const [open, setOpen] = useState(false);
  const { isAuthenticated, user, role, organizationId } = useSession();
  const { logout } = useLogout();

  const items = isAuthenticated
    ? [
        {
          label: "Preferences",
          icon: Settings,
          onSelect: () => {
            /* No preferences page exists yet — the item is present per
             * §18's own contract, wired once one does. */
          },
        },
        { label: "Documentation", icon: HelpCircle, onSelect: () => window.open(HELP_URL, "_blank", "noopener") },
        {
          label: "Sign out",
          icon: LogOut,
          destructive: true,
          onSelect: () => void logout(),
        },
      ]
    : [{ label: "Documentation", icon: HelpCircle, onSelect: () => window.open(HELP_URL, "_blank", "noopener") }];

  return (
    <Dropdown
      open={open}
      onClose={() => setOpen(false)}
      align="end"
      trigger={
        <IconButton
          icon={isAuthenticated ? CircleUserRound : Sparkles}
          aria-label={isAuthenticated && user ? `Account menu for ${user.email}` : "Account menu"}
          variant="ghost"
          onClick={() => setOpen((value) => !value)}
        />
      }
      items={items}
      header={
        isAuthenticated ? (
          <div className="border-border mb-1 flex flex-col gap-0.5 border-b px-2 pt-1 pb-2">
            <p className={typography.label}>{user?.email ?? "…"}</p>
            <p className="text-muted-foreground text-xs">Role: {role ?? "Not assigned"}</p>
            <p className="text-muted-foreground text-xs">
              Organization: {organizationId ?? "No organization"}
            </p>
          </div>
        ) : undefined
      }
    />
  );
}
