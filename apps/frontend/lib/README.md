# lib/

Thin, self-contained wrappers around a single concern that isn't quite a
pure function (→ `utils/`) and isn't feature-specific (→
`features/<feature>/utils/`) — e.g. `route-registry.ts`, the centralized
route-metadata registry docs/frontend Prompt 001 §15 asks for.

Keep this directory small. If something here starts accumulating
feature-specific branches, it belongs in a feature module instead.
