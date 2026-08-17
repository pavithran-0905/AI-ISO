/** A safe, same-app redirect target: must be a path (not a full URL) so
 * a crafted `?from=https://evil.example` (or the `//evil.example`
 * protocol-relative variant) can never send a signed-in user off-site
 * (docs/frontend Prompt 004 §9: "Do not allow unsafe external redirect
 * URLs. Validate return destinations."). Kept out of `auth/guards.tsx`
 * (a "use client" module) so server components can call it directly —
 * every export of a client-boundary file becomes a client reference,
 * which Next.js refuses to invoke outside of JSX/props on the server. */
export function isSafeReturnPath(path: string | undefined | null): path is string {
  if (!path) return false;
  if (!path.startsWith("/")) return false;
  if (path.startsWith("//")) return false;
  if (path.startsWith("/\\")) return false;
  return true;
}
