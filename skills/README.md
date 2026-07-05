# Skills

Skills are lightweight, on-demand documents that an agent loads when a task
requires specific expertise. They are **not** required reading at onboarding —
`AGENTS.md` is the single entry point.

## Rules (per the founding brief, §3 lesson 4)

1. Each skill is **self-contained** — no cross-skill dependencies.
2. Each skill is **≤200 lines** — if a skill needs more, split it.
3. Skills are loaded **only when a task requires them** — never as a
   prerequisite for adoption.
4. Skills live in `skills/` at the workspace root (project-level skills)
   or in the installed package's `skills/` directory (framework-level skills).
5. A skill is plain markdown with optional CORTEX sections (no YAML, no JSON).
6. Skills are discovered by the agent via `ls skills/` or via a skill index
   file (`skills/INDEX.md`) — never via a global registry.

## Format

A skill file has the structure:

```markdown
# <skill-name> — <one-line description>

## When to use
- Trigger conditions

## What to do
- Step-by-step instructions

## Examples
- Concrete before/after or sample outputs

## References
- Links to source material
```

## Available skills

This package ships with the following framework-level skills:

- `governance-bootstrap.md` — how to initialize a fresh workspace
- `evidence-capture.md` — how to record evidence efficiently
- `cycle-retrospective.md` — how to run a post-cycle review as an auditor

Each skill is auto-loaded by the agent on demand. To add a new skill,
drop a `.md` file into this directory and update `INDEX.md`.
