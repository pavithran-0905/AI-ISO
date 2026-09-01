"use client";

import type { LucideIcon } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/data-display/card";
import { getRouteById, type RouteMeta } from "@/lib/route-registry";
import { usePermissions } from "@/permissions/hooks";

const QUICK_ACCESS_ROUTE_IDS = [
  "infrastructure",
  "monitoring",
  "alerting",
  "automation",
  "reporting",
  "infrastructure-topology",
  "operations-workspace",
] as const;

/**
 * Resource Quick Access (§23) — titles/icons/paths/`roles` read
 * straight from the canonical route registry (§47: "use canonical
 * route registry"), never a second, hand-written nav list. Filtered
 * the same way `PrimaryNavigation` filters the sidebar itself
 * (`route.roles === null || (role !== null && route.roles.includes(role))`)
 * so a module hidden from this user's sidebar is never surfaced here
 * either (§27/§49). Icon-less routes (every sub-route in the registry
 * — only top-level entries carry one, by convention) are skipped
 * defensively rather than rendered with no icon.
 */
export function QuickAccessGrid() {
  const { role } = usePermissions();

  const tiles = QUICK_ACCESS_ROUTE_IDS.map((id) => getRouteById(id)).filter(
    (route): route is RouteMeta & { icon: LucideIcon } =>
      route !== undefined && route.icon !== null && (route.roles === null || (role !== null && route.roles.includes(role))),
  );

  if (tiles.length === 0) return null;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {tiles.map((route) => {
        const Icon = route.icon;
        return (
          <Link
            key={route.id}
            href={route.path}
            className="focus-visible:ring-ring block rounded-lg focus-visible:ring-2 focus-visible:outline-none"
          >
            <Card className="hover:border-muted-foreground/50 flex flex-col items-start gap-2 p-4 transition-colors">
              <Icon className="text-muted-foreground size-5" aria-hidden="true" />
              <span className="text-sm font-medium">{route.navLabel ?? route.title}</span>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
