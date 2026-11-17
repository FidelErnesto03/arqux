---
doc_type: guide
status: normative
version: 1.0.0
verified: 2026-11-15
---

<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../../docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="../../../docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>Guide · Normative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Booting an agent with governed context

*English translation — canonical source: `docs/es/guias/arranque-agente.md`*

`arqux wake --identity <role>` delivers the agent's context in a single call: **who it is, which projects exist, what state the work is in, which rules apply and which task is in flight**. It is the governed replacement for the bloated system prompt.

Real measurements in this workspace: **183 ms**, **2,875 bytes** (~800 tokens — under the <1500 budget declared in REQ-08), `cortex:1.0` output.

```bash
arqux wake --identity executor --path /path/to/workspace
```

## What it returns — annotated real output

```cortex
$0
$0:format{cortex:1.0, encoding:UTF-8}
ARQX:arqx_contract{...} DOM:dom_contract{...} IDN:idn_contract{...} ...

$19: ARQUX METADATA
ARQX:artifact{level:0, name:"wake-executor", usage:"state", kind:"projection"}

$1: WAKE
IDN:wake{identity:"executor", kind:"generic",
         workspace:"/home/vatrox/workspace", project:"none", cycle:"none"}

$2: REGISTRY
DOM:arqux{name:"ARQUX", status:"current", updated:"2026-11-15T22:05:56Z",
          last_event:"blueprint.complete"}
DOM:codec_cortex{name:"CODEC-CORTEX", status:"current", ...}
...                                       ← workspace projects, with last event

$3: STATE
WRK:current{name:"workspace", project:"Proyecto_X", scope:"CYCLE-01",
            agent:"Alfred", phase:"consolidation", current:"GRADIENT-12 aplicado",
            state:"iter4_done", task:"VAMOS loop iter-4: ...", pendiente:"..."}

$4: RULES

$5: TASK
TSK:none{task_id:"none", note:"no in-progress task"}
```

| Section | Content | What it gives the agent |
|---|---|---|
| `$0` + contracts | Self-contained local glossary | The file parses alone, no external context |
| `$1 WAKE` | Identity, kind, workspace, project, cycle | "Who I am and where I am" |
| `$2 REGISTRY` | `DOM:` per project: status, cycle, last event | The workspace map without exploring |
| `$3 STATE` | `WRK:current`: focus, phase, task, pending | "What was going on" — real continuity |
| `$4 RULES` | Applicable policy rules | "What I cannot do" |
| `$5 TASK` | In-flight task or `TSK:none` | "What I do now" |

> Example captured from the real workspace; a minimal workspace shows fewer `DOM:` entries — the structure is the same.

## Valid roles and identities

`--identity` accepts any identity registered in `.arqux/identities/*.cortex`. In this workspace: `alfred`, `auditor`, `executor`, `governor`, `heimdall`, `jarvis`, `seshat`.

A nonexistent role produces an error plus the list of valid ones (exit 1):

```bash
$ arqux wake --identity fulano --path /workspace
unknown identity 'fulano'. Valid contracts: alfred, auditor, executor, governor, heimdall, jarvis, seshat
```

## Bootstrap integration

Three concrete places where `wake` replaces hand-written context:

**1. Before the first turn (harness session hook).**

```bash
# in your agent wrapper/entrypoint
WAKE=$(arqux wake --identity executor --path "$WORKSPACE")
# → inject $WAKE as the LLM's first context message
```

The agent starts knowing the workspace's real state — not what a week-old system prompt claimed.

**2. In AGENTS.md as a boot instruction.**

```markdown
## Boot
Before acting: run `arqux wake --identity executor --path <workspace>`
and treat its output as your current state.
```

Works in any harness that reads AGENTS.md (see [multi-harness projection](proyectar-agentes.md)) — the agent self-bootstraps.

**3. Periodic refresh in long sessions.**

After a milestone (task close, cycle switch), re-run `wake` — REGISTRY and STATE reflect the new point. 183 ms makes refreshing cheap.

## Honest notes

- **`kind:"generic"`**: the payload describes identity+registry+state; it does not include the identity's full behavioral contract (that lives in `.arqux/identities/<id>.cortex`).
- **Known diagnostic:** if two workspace projects share a name, their `DOM:` entries collide and the codec reports `I006_DUPLICATE_IDEA_ADDRESS` on validation — verified in this workspace. The output stays readable; name deduplication is pending generator work.
- Output changes with state: `WRK:current` and `TSK:` reflect what exists *now*, not a fixed template.

## Cheatsheet

| I want | Command |
|---|---|
| Boot context for an agent | `arqux wake --identity <role> --path <ws>` |
| See valid roles | `ls .arqux/identities/` (or trigger the error — it lists them) |
| Refresh state mid-session | re-run `wake` (183 ms) |

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
