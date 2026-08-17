import { AuthGuard } from "@/auth/guards";
import { MainLayout } from "@/layouts/main-layout";

/**
 * Every route under this group renders inside the Main Enterprise
 * Application Layout, gated by `AuthGuard` (docs/frontend Prompt 004
 * §10) — an unauthenticated visitor is redirected to `/login` before
 * the shell chrome (or the page) ever renders. The `(auth)` route
 * group (login) uses `AuthLayout` instead, deliberately outside this
 * guard.
 */
export default function AppRouteGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <MainLayout>{children}</MainLayout>
    </AuthGuard>
  );
}
