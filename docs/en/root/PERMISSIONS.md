---
doc_type: reference
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
<p align="center"><sub>Reference · Normative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# ArqUX permissions model

> The §4 table is **generated from the live registry** (`python scripts/generate_permissions_md.py --lang en --write docs/en/root/PERMISSIONS.md`). It is never hand-edited: if the registry changes, regenerate.

English twin of the canonical [`PERMISSIONS.md`](../../../PERMISSIONS.md). ArqUX controls who may invoke each handler along two independent axes:

1. **Agent role** — resolved from the session context (`ARQUX_AGENT_ROLE` as transport fallback). `src/arqux/permissions.py`.
2. **Policy-rule enforce level** — `CODE | PROMPT | HUMAN` in `learn-policies.cortex`. `src/arqux/core/policy_engine.py`.

---

## 1. Roles

| Role | Identities | Access |
|---|---|---|
| **GOVERNOR** | `alfred` | All 115 handlers. The only role that can run `GOVERNOR_ONLY` (`workspace.init`, `project.init`). |
| **EXECUTOR** | `jarvis` | Everything except `GOVERNOR_ONLY`. |
| **AUDITOR** | `heimdall`, `seshat` | Read-only. The model is a **denylist**: any handler except `GOVERNOR_ONLY`, `MUTATING_HANDLERS`, and the mutating invocations of `CONDITIONAL_MUTATING` is callable. Previews and `dry_run` remain allowed. |

Real example: `heimdall` (AUDITOR) can call `cortex.read`, `blueprint.read` and `session.resume` — those are reads — but `blueprint.ac` returns `PERMISSION_DENIED` because it mutates. That is why in this project Heimdall **audits and reports** while the governor **signs** the criteria.

The identity→role mapping lives in `permissions.py` (`alfred`→GOVERNOR, `jarvis`→EXECUTOR, `heimdall`/`seshat`→AUDITOR).

## 2. HMAC verification

Three handlers additionally require an HMAC-SHA256 signature on top of the role — they prove the caller **is** who it claims to be:

- `identity.record` — otherwise anyone could sign a lesson as another agent
- `evidence.record` — evidence must be attributable to a verified agent
- `blueprint.re_delegate` — re-delegation is an act of governance

The signature binds `agent_id | handler | timestamp | payload_hash` (anti-replay). With `ARQUX_STRICT_SECURITY=1` it is always verified; without it, legacy mode applies.

## 3. Policy enforce levels

The `RUL`/`POL`/`GTE`/`THR`/`KNW`/`PRT`/`IDN` rules in `learn-policies.cortex` **must** declare `enforce`; its absence produces `ERR_MISSING_ENFORCE_LEVEL` (REQ-10, fail-closed on malformed rules).

| Level | Executes | Real example |
|---|---|---|
| `CODE` | The runtime as a pre/post-write hook via `evaluate_hooks()` | `RUL:no_secret_commit` — `check:"secret_pattern"` blocks governed writes containing API keys or private keys (`POLICY_BLOCK`). Native check in `policy_engine.py`. |
| `PROMPT` | Rendered into the agent's context (AGENTS.md / `wake` payload) | Mechanism implemented in `policy_engine.py`; **no PROMPT rule deployed in this workspace today** (verified 2026-11-15). |
| `HUMAN` | Explicit human gate — the runtime exposes it, never auto-applies | `POL:candidate_elevation` — `requires:"user_confirmation"` to elevate candidates into lessons. |

## 4. Authorization table — 115 handlers

`Minimum role` = the lowest role that can invoke the handler. `EXECUTOR*` marks `CONDITIONAL_MUTATING` handlers: the auditor is denied only when the listed flags are truthy (and `dry_run` falsy).

<!-- GENERATED:PERMISSIONS_TABLE — regenerate: python scripts/generate_permissions_md.py --lang en --write docs/en/root/PERMISSIONS.md -->
<!-- 115 handlers — generated from REGISTRY + permissions.py -->
| Handler | Minimum role | HMAC | Condition |
|---|---|---|---|
| `blueprint.ac` | EXECUTOR | no | mutates — auditor denied |
| `blueprint.block_for_architect` | EXECUTOR | no | mutates — auditor denied |
| `blueprint.cancel` | EXECUTOR | no | mutates — auditor denied |
| `blueprint.claim` | EXECUTOR | no | mutates — auditor denied |
| `blueprint.complete` | EXECUTOR | no | mutates — auditor denied |
| `blueprint.create` | EXECUTOR | no | mutates — auditor denied |
| `blueprint.execute` | EXECUTOR | no | mutates — auditor denied |
| `blueprint.fail` | EXECUTOR | no | mutates — auditor denied |
| `blueprint.frontmatter.update` | AUDITOR | no | read |
| `blueprint.list` | AUDITOR | no | read |
| `blueprint.re_delegate` | EXECUTOR | yes | mutates — auditor denied |
| `blueprint.read` | AUDITOR | no | read |
| `blueprint.ready` | EXECUTOR | no | mutates — auditor denied |
| `blueprint.synthesize` | EXECUTOR | no | mutates — auditor denied |
| `blueprint.task` | EXECUTOR | no | mutates — auditor denied |
| `blueprint.update` | EXECUTOR | no | mutates — auditor denied |
| `context.detect` | AUDITOR | no | read |
| `context.full` | AUDITOR | no | read |
| `cortex.checkpoint` | EXECUTOR | no | mutates — auditor denied |
| `cortex.corpus.list` | AUDITOR | no | read |
| `cortex.corpus.query` | AUDITOR | no | read |
| `cortex.entry.add` | EXECUTOR | no | mutates — auditor denied |
| `cortex.entry.delete` | EXECUTOR | no | mutates — auditor denied |
| `cortex.entry.get` | AUDITOR | no | read |
| `cortex.entry.list` | AUDITOR | no | read |
| `cortex.entry.move` | EXECUTOR | no | mutates — auditor denied |
| `cortex.entry.update` | EXECUTOR | no | mutates — auditor denied |
| `cortex.file.validate` | EXECUTOR* | no | auditor denied if `fix` |
| `cortex.format` | AUDITOR | no | read |
| `cortex.gc` | EXECUTOR* | no | auditor denied if `force` |
| `cortex.learn` | AUDITOR | no | read |
| `cortex.learn.elevate` | EXECUTOR* | no | auditor denied if `apply` |
| `cortex.migrate` | EXECUTOR* | no | no flag — always mutates; dry_run/preview allow reads |
| `cortex.patch` | EXECUTOR* | no | no flag — always mutates; dry_run/preview allow reads |
| `cortex.read` | AUDITOR | no | read |
| `cortex.ref` | AUDITOR | no | read |
| `cortex.render` | AUDITOR | no | read |
| `cortex.render.diagram` | AUDITOR | no | read |
| `cortex.render.validate_file` | AUDITOR | no | read |
| `cortex.verify` | AUDITOR | no | read |
| `cortex.write` | EXECUTOR | no | mutates — auditor denied |
| `cycle.close` | EXECUTOR | no | mutates — auditor denied |
| `cycle.create` | EXECUTOR | no | mutates — auditor denied |
| `cycle.current` | AUDITOR | no | read |
| `cycle.list` | AUDITOR | no | read |
| `cycle.reopen` | AUDITOR | no | read |
| `cycle.synthesize` | EXECUTOR | no | mutates — auditor denied |
| `evidence.list` | AUDITOR | no | read |
| `evidence.read` | AUDITOR | no | read |
| `evidence.record` | EXECUTOR | yes | mutates — auditor denied |
| `handler.how_to` | AUDITOR | no | read |
| `handler.list` | AUDITOR | no | read |
| `identity.elevate` | EXECUTOR* | no | auditor denied if `apply` |
| `identity.get` | AUDITOR | no | read |
| `identity.record` | EXECUTOR | yes | mutates — auditor denied |
| `identity.switch` | EXECUTOR | no | mutates — auditor denied |
| `issue.create` | EXECUTOR | no | mutates — auditor denied |
| `issue.list` | AUDITOR | no | read |
| `issue.read` | AUDITOR | no | read |
| `issue.update` | EXECUTOR | no | mutates — auditor denied |
| `loop.activate` | AUDITOR | no | read |
| `loop.advance` | AUDITOR | no | read |
| `loop.complete` | AUDITOR | no | read |
| `loop.deactivate` | AUDITOR | no | read |
| `loop.list` | AUDITOR | no | read |
| `loop.register` | AUDITOR | no | read |
| `loop.remove` | AUDITOR | no | read |
| `loop.suggest` | AUDITOR | no | read |
| `loop.wake` | AUDITOR | no | read |
| `project.bind` | EXECUTOR | no | mutates — auditor denied |
| `project.init` | GOVERNOR | no | governor only |
| `project.lessons` | AUDITOR | no | read |
| `project.status` | AUDITOR | no | read |
| `project.unbind` | EXECUTOR | no | mutates — auditor denied |
| `protocol.adopt` | EXECUTOR | no | mutates — auditor denied |
| `protocol.onboard` | EXECUTOR | no | mutates — auditor denied |
| `protocol.pause` | EXECUTOR | no | mutates — auditor denied |
| `protocol.release` | EXECUTOR | no | mutates — auditor denied |
| `protocol.resume` | EXECUTOR | no | mutates — auditor denied |
| `session.bootstrap` | EXECUTOR | no | mutates — auditor denied |
| `session.close` | EXECUTOR | no | mutates — auditor denied |
| `session.context.get` | AUDITOR | no | read |
| `session.context.set` | EXECUTOR | no | mutates — auditor denied |
| `session.handoff` | EXECUTOR | no | mutates — auditor denied |
| `session.pulse.compact` | EXECUTOR | no | mutates — auditor denied |
| `session.pulse.gc` | EXECUTOR* | no | no flag — always mutates; dry_run/preview allow reads |
| `session.resume` | AUDITOR | no | read |
| `session.status` | AUDITOR | no | read |
| `setup.plantuml` | EXECUTOR | no | mutates — auditor denied |
| `skill.convert` | EXECUTOR | no | mutates — auditor denied |
| `skill.edit` | EXECUTOR* | no | auditor denied if `content` |
| `skill.evolve` | EXECUTOR* | no | auditor denied if `apply` |
| `skill.get` | AUDITOR | no | read |
| `skill.import` | EXECUTOR | no | mutates — auditor denied |
| `skill.install` | EXECUTOR | no | mutates — auditor denied |
| `skill.list` | AUDITOR | no | read |
| `skill.record` | EXECUTOR | no | mutates — auditor denied |
| `sync.reconcile` | EXECUTOR | no | mutates — auditor denied |
| `sync.run` | EXECUTOR | no | mutates — auditor denied |
| `task.claim` | EXECUTOR | no | mutates — auditor denied |
| `task.complete` | EXECUTOR | no | mutates — auditor denied |
| `task.create` | EXECUTOR | no | mutates — auditor denied |
| `task.fail` | EXECUTOR | no | mutates — auditor denied |
| `task.list` | AUDITOR | no | read |
| `task.read` | AUDITOR | no | read |
| `task.run` | EXECUTOR | no | mutates — auditor denied |
| `task.update` | EXECUTOR | no | mutates — auditor denied |
| `timelog.project` | EXECUTOR* | no | auditor denied if `action!=preview` |
| `timelog.purge` | EXECUTOR* | no | auditor denied if except `preview` |
| `timelog.query` | AUDITOR | no | read |
| `timelog.review` | EXECUTOR | no | mutates — auditor denied |
| `timelog.summary` | AUDITOR | no | read |
| `workspace.init` | GOVERNOR | no | governor only |
| `workspace.lessons` | AUDITOR | no | read |
| `workspace.status` | AUDITOR | no | read |
<!-- /GENERATED:PERMISSIONS_TABLE -->

## 5. Denial and elevation

| Situation | Result | Reference |
|---|---|---|
| Auditor invokes a mutating handler | `PERMISSION_DENIED` (the server translates `PermissionDenied` → MCP/CLI error; treat as 403) | `../referencia/errores.md` |
| `enforce:CODE` rule with `action:"deny"` fires | `POLICY_BLOCK` — read the blocking rule (`pull-policy`), fix the content | `core/policy_engine.py` |
| `HMAC_REQUIRED` handler without a valid signature | `PERMISSION_DENIED` / invalid signature | `security.py` |
| Current role insufficient | Request elevation: `identity.elevate` (conditional, `apply` flag) or run `arqux elevate` — escalates to the HUMAN gate | `cli.py` |

Legacy mode: without `ARQUX_STRICT_ROLES=1` the role check is lax (historical governor bypass). **Never use lax mode to bypass a denial** — the denial is a design signal.

## 6. Environment variables

Those governing authorization (defined in `constants.py` / `permissions.py`):

| Variable | Effect |
|---|---|
| `ARQUX_AGENT_ID` | Transport identity (fallback; session context wins) |
| `ARQUX_AGENT_ROLE` | Agent role: `GOVERNOR`/`EXECUTOR`/`AUDITOR` (default GOVERNOR) |
| `ARQUX_AGENT_SECRET` | Agent HMAC secret |
| `ARQUX_AGENT_SIGNATURE` / `ARQUX_AGENT_TIMESTAMP` | Precomputed HMAC signature + timestamp |
| `ARQUX_EXECUTION_KEY` | Strict-execution key |
| `ARQUX_STRICT_ROLES=1` | Forces role check (without it: legacy bypass) |
| `ARQUX_STRICT_SECURITY=1` | Forces HMAC verification on `HMAC_REQUIRED` |
| `ARQUX_STRICT_EXECUTION=1` | Forces execution key |
| `ARQUX_ALLOW_IMPLICIT_EXECUTION` | Allows implicit execution |
| `ARQUX_SUSPENDED` | Suspends governed operation |
| `ARQUX_ENV_PREFIX` | Alternate prefix for all vars |
| `ARQUX_METADATA` | Session/agent metadata |

Additional families (not authorization, listed for completeness): `ARQUX_DIR`, `ARQUX_VERSION`, `ARQUX_FORMAT_DECL`, `ARQUX_GLOSSARY_TEXT`, `ARQUX_META_*` (SIGIL/SECTION/TITLE/ENTRY/PRIORITY), `ARQUX_HOST_BRIDGE_SOCKET`, `ARQUX_COMMS_*` (TELEGRAM_TOKEN, ALLOWLIST, EGRESS), `ARQUX_VOICE_*`. Full inventory: `../referencia/configuracion.md`.

## 7. How to regenerate the table

```bash
python scripts/generate_permissions_md.py --write PERMISSIONS.md                 # ES canon
python scripts/generate_permissions_md.py --lang en --write docs/en/root/PERMISSIONS.md  # EN twin
```

The script imports `arqux.handlers.REGISTRY` and the sets from `arqux.permissions` (`GOVERNOR_ONLY`, `MUTATING_HANDLERS`, `CONDITIONAL_MUTATING`, `HMAC_REQUIRED`) and emits the 115 rows in deterministic order. If the count differs from `handler.list`, the table is stale — regenerate, never patch by hand.

## References

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — layers and handler→policy→state flow
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — why each control exists
- `../referencia/errores.md` — `PERMISSION_DENIED` / `POLICY_BLOCK` codes
- `../referencia/configuracion.md` — full env vars
- `../../../HANDLERS.md` — signature and description of each handler (generated, ES canonical)

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
