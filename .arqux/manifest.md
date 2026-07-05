# Workspace Manifest — Arqux Self-Governance

This workspace governs the development of Arqux itself.

## Bootstrap
The first agent to call `workspace.init` on this directory became the
governor by default. Subsequent agents must call `protocol.adopt` with
a role assigned by the governor.

## Cycles
- `CYCLE-00` — initial skeleton + placeholder rename support (this cycle)
- `CYCLE-01` — workspace + project + cycle handlers (Phase 1)
- `CYCLE-02` — task handlers (Phase 2)
- `CYCLE-03` — identities and permissions (Phase 3)
- `CYCLE-04` — installability and CLI (Phase 4)
- `CYCLE-05` — AGENTS.md unification (Phase 5)
- `CYCLE-06` — tests and publication (Phase 6)
- `CYCLE-99` — release v1.0 (Phase 7)

## Metadata
- **version:** 1.0.0
- **product:** arqux
- **governor:** bootstrap
- **status:** active
