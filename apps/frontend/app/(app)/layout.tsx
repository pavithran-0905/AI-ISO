import { MainLayout } from "@/layouts/main-layout";

/**
 * Every route under this group renders inside the Main Enterprise
 * Application Layout. A future `(auth)` route group (login, register, MFA
 * challenge) will use `AuthLayout` instead.
 *
 * `AuthGuard` (see `@/auth/guards`) is deliberately NOT applied here yet:
 * no login page exists in this prompt (per docs/frontend Prompt 001 §13,
 * "Do NOT build the complete login UI yet"), so gating this route group
 * now would redirect to a route that doesn't exist and break the one
 * working page in the app. Wire `<AuthGuard>` in here once the login flow
 * ships.
 */
export default function AppRouteGroupLayout({ children }: { children: React.ReactNode }) {
  return <MainLayout>{children}</MainLayout>;
}
