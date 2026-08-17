/**
 * Centralized route metadata (docs/frontend Prompt 001 §15). Next.js App
 * Router's routes are file-system-defined (`app/**\/page.tsx`), so this
 * registry doesn't declare routing itself — it's the single source of
 * truth for the metadata *about* each route (title, breadcrumb,
 * permission, nav visibility) that a future primary-navigation component
 * and breadcrumb trail will both read, so they can never disagree about
 * what a route is called or who can see it.
 *
 * Only routes that exist are registered — do not pre-register a future
 * feature's route before its `page.tsx` exists (docs/frontend Prompt 001
 * §9 forbids building those pages in this prompt).
 */

import type { Role } from "@/auth/types";

export interface RouteMeta {
  path: string;
  title: string;
  breadcrumb: string;
  /** `null` means no role restriction (every authenticated user). */
  roles: Role[] | null;
  /** Which `features/<feature>` module owns this route, for traceability
   * back to docs/frontend/backend-feature-matrix.md. `null` for
   * foundation-only routes that don't belong to a business feature. */
  feature: string | null;
  showInNav: boolean;
}

export const ROUTE_REGISTRY: readonly RouteMeta[] = [
  {
    path: "/",
    title: "Dashboard",
    breadcrumb: "Dashboard",
    roles: null,
    feature: null,
    showInNav: true,
  },
];

export function getRouteMeta(path: string): RouteMeta | undefined {
  return ROUTE_REGISTRY.find((route) => route.path === path);
}

export function getNavRoutes(): RouteMeta[] {
  return ROUTE_REGISTRY.filter((route) => route.showInNav);
}
