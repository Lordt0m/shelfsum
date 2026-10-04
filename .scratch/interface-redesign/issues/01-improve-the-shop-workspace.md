# Improve the shop workspace

Status: in-progress

Implement the interface-redesign specification as one coherent vertical slice. Preserve all existing mutation services, permissions and report/CSV semantics. Add regression coverage at the request boundary for filters/pagination, ledger-derived history and non-mutating previews, and verify responsive layouts in the browser.

## Comments

Started from clean main c546e3a in isolated codex/interface-redesign worktree. The employability research clone is not the source of this change. The supplied references and frontend-design guidance drive the token system, functional hierarchy and responsive treatment.
