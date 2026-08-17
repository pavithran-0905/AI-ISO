/**
 * Authentication Layout (docs/frontend Prompt 001 §16) — the centered,
 * chrome-free shell for login/register/MFA-challenge pages. Not yet
 * wired into `app/`; see `app/(app)/layout.tsx` for why no login page
 * exists in this prompt. Ready for a future `app/(auth)/layout.tsx` to
 * import once one does.
 */
export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-background text-foreground flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="text-lg font-semibold tracking-tight">AI-IOS</span>
        </div>
        {children}
      </div>
    </div>
  );
}
