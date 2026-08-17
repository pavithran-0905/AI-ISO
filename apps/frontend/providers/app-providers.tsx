import { AuthBootstrap } from "@/auth/session";
import { ToastViewport } from "@/components/feedback/toast";
import { QueryProvider } from "@/providers/query-provider";
import { ThemeProvider } from "@/providers/theme-provider";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <QueryProvider>
        <AuthBootstrap>
          {children}
          <ToastViewport />
        </AuthBootstrap>
      </QueryProvider>
    </ThemeProvider>
  );
}
