import { AuthLayout } from "@/layouts/auth-layout";

/**
 * Every route under this group renders inside the chrome-free
 * `AuthLayout` (login, and any future register/MFA-challenge page) —
 * the counterpart to `app/(app)/layout.tsx`'s `MainLayout`, per the
 * routing split documented in `docs/frontend/architecture/routing.md`.
 */
export default function AuthRouteGroupLayout({ children }: { children: React.ReactNode }) {
  return <AuthLayout>{children}</AuthLayout>;
}
