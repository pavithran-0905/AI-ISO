# Naming Conventions

- **Files**: kebab-case (`error-state.tsx`, `route-registry.ts`,
  `split-pane-layout.tsx`). Test files mirror their source's path under
  `tests/unit/`, suffixed `.test.ts`/`.test.tsx`
  (`layouts/wizard-layout.tsx` → `tests/unit/layouts/wizard-layout.test.tsx`).
- **Components**: PascalCase, matching the file's primary export
  (`EmptyState`, `MainLayout`, `RequirePermission`).
- **Hooks**: `use` prefix, camelCase (`useSession`, `usePermissions`,
  `useHasRole`).
- **Zustand stores**: `use<Noun>Store` (`useAuthStore`, `useThemeStore`),
  the underlying state file named after the noun
  (`auth/store.ts`, `state/theme-store.ts`).
- **Types/interfaces**: PascalCase, no `I`/`T` prefix
  (`AuthUser`, `RouteMeta`, not `IAuthUser`).
- **API client methods**: lowercase HTTP verbs (`apiClient.get`,
  `.post`, `.put`, `.patch`, `.delete`), matching `fetch`'s own
  vocabulary rather than inventing REST-resource-shaped names.
- **Error classes**: `<Domain>Error` (`ApiRequestError`,
  `ApiTimeoutError`, `ApiNetworkError`, `TransitionRefusedError`-style
  naming carried over from the backend's own convention).
- **Backend field names stay snake_case at the API boundary, become
  camelCase past it.** `auth/api.ts` is the explicit translation layer
  (`display_name` → `displayName`) — nothing past that file should ever
  see a snake_case field name.
