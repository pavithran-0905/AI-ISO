import { Footer } from "@/layouts/main/footer";
import { Header } from "@/layouts/main/header";

/**
 * The Main Enterprise Application Layout (docs/frontend Prompt 001, §16).
 * Wraps every protected route via `app/(app)/layout.tsx`. Primary
 * navigation, breadcrumbs, and command palette are added incrementally by
 * later frontend prompts — this establishes the composition point.
 */
export function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-background text-foreground flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 p-6">{children}</main>
      <Footer />
    </div>
  );
}
