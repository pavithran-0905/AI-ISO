import { Breadcrumbs } from "@/components/navigation/breadcrumbs";
import { PrimaryNavigation } from "@/components/navigation/primary-navigation";
import { Footer } from "@/layouts/main/footer";
import { Header } from "@/layouts/main/header";

/**
 * The Main Enterprise Application Layout (docs/frontend Prompt 001
 * §16, completed by Prompt 003 §5's shell structure): global header on
 * top, primary navigation down the left, breadcrumbs + page content in
 * the remaining column. A page's own `PageHeader` and contextual
 * actions live inside `{children}` — this layout only owns the shell
 * chrome, never feature content.
 */
export function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-background text-foreground flex min-h-screen flex-col">
      <Header />
      <div className="flex min-h-0 flex-1">
        <PrimaryNavigation />
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="border-border border-b px-6 py-2">
            <Breadcrumbs />
          </div>
          <main className="flex-1 p-6">{children}</main>
        </div>
      </div>
      <Footer />
    </div>
  );
}
