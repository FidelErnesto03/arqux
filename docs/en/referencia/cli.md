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

# `arqux` CLI reference

*English translation — canonical source: `docs/es/referencia/cli.md`*

Exhaustive reference of the ArqUX 1.0.0 CLI: every command, every flag, every exit code, one real executed example. Single source of truth: the click tree in `src/arqux/cli.py` — if this page differs from the code, the page lies.

## Conventions

- `arqux <cmd> --help` is always authoritative over this page.
- `--path` exists on several commands; default: current directory.
- `arqux call <handler> key=value` invokes any handler without MCP — handler args are inline `key=value`.
- Environment variables (`ARQUX_AGENT_ID`, `ARQUX_AGENT_ROLE`, `ARQUX_STRICT_*`): see `docs/en/referencia/configuracion.md`.
- Exit codes: 0 success; 1 functional error or failed verification; 2 usage error (click parser). Symbolic codes (`ERR_*`, `EXPORT_BLOCKED`) are documented per command.

## Summary table

| Command | Purpose | Group |
|---|---|---|
| `init` | Initialize `.arqux/` | Start |
| `quickstart` | Guided workspace onboarding | Start |
| `status` | Workspace+project+cycle status | Inspection |
| `doctor` | Health diagnostic with `--fix` | Inspection |
| `call` | Invoke a handler directly | Governance |
| `cycle`, `project` | Shortcuts to `cycle.*`/`project.*` handlers | Governance |
| `handlers` | List available handlers | Governance |
| `validate` | Validate a `.cortex` | CORTEX |
| `cortex-verify` | Verify SHA-256 seal | CORTEX |
| `cortex-migrate` | Migrate legacy format to CODEC 1.0 | CORTEX |
| `migrate` | Inject `ARQX:artifact` into a `.cortex` | CORTEX |
| `elevate` | Elevate a lesson (dry-run by default) | CORTEX |
| `review` | Cycle → HCORTEX Markdown | Reports |
| `from-hcortex` | HCORTEX → `.cortex` (round-trip) | Reports |
| `evidence export` | Evidence bundle with privacy gate | Evidence |
| `policy keygen/sign/verify` | Ed25519 for artifacts | Evidence |
| `backup`, `restore` | `.tar.gz` backup + restore | Operations |
| `push-delta`, `pull-policy` | Authoritative policy journal | Sync |
| `sync-harnesses`, `drift-check` | Projection to AGENTS/CLAUDE/GEMINI + drift | Sync |
| `loop-watch` | Watch autonomous loops | Sync |
| `wake` | Dense boot payload for agents | Agents |
| `identity list/resolve/elevate` | Agent identities | Agents |
| `skill list/resolve/import` | Skills with provenance | Agents |
| `serve` | MCP server over stdio | Services |
| `session-bridge serve` | Host-bridge broker (Unix socket) | Services |
| `serve-plantuml`, `setup-plantuml`, `render-diagram` | Diagram rendering | Services |
| `comms-serve`, `comms-doctor` | Comms extension (`arqux[comms]`) | Extensions |
| `voice-serve`, `voice-doctor`, `voice-daemon` | Voice extension (`arqux[voice]`) | Extensions |

---

## Start and status

### `arqux init`

Initializes `.arqux/` in the directory. On an already-governed workspace it aborts without `--force` — it never overwrites `.arqux/*.cortex`.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--path` | text | cwd | Path to initialize |
| `--verbose` | flag | off | OUT-AUDIT profile |
| `--force` | flag | off | Re-initialize governed workspace |

```bash
$ arqux init --path /tmp/ws
OUT-MIN workspace=/tmp/ws/.arqux governor=anonymous workspace.init ok
```

### `arqux quickstart`

Guided onboarding: validates governed workspace + `AGENTS.md` and lists next steps (identity, role, first commands).

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--path` | text | cwd | Directory to bootstrap |

```bash
$ arqux quickstart --path /tmp/ws
✅ Workspace already governed at /tmp/ws
📋 Next steps:
  1. Set your identity:     export ARQUX_AGENT_ID=<name>
  2. Set your role:         export ARQUX_AGENT_ROLE=governor|executor|auditor
```

### `arqux status`

Combined status: workspace, active project, cycle.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--path` | text | cwd | Path to inspect |
| `--verbose` | flag | off | Extended output |
| `--dashboard` | flag | off | Visual dashboard |

```bash
$ arqux status --path /tmp/ws
OUT-MIN workspace=/tmp/ws/.arqux manifest=true meta_brain=True
OUT-ERROR code=NOT_FOUND no project initialized
```

### `arqux doctor`

Workspace/project health diagnostic (8+ checks). `--fix` applies repairs.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--fix` | flag | off | Apply automatic repairs |

```bash
$ arqux doctor
OUT-WORK context=workspace checks=8 passed=8 failed=0 warned=0
  [✅] nested .arqux: No .arqux inside .arqux
  [✅] meta-brain.cortex: ok (4096 bytes)
```

---

## Governance

### `arqux call HANDLER [key=value ...]`

Invokes any handler directly — no MCP server. The debugging and scripting form.

```bash
$ arqux call workspace.status
OUT-MIN workspace=/tmp/ws/.arqux manifest=true …
$ arqux call blueprint.list status=done cycle=CYCLE-16
```

### `arqux cycle SUB [ARGS]`, `arqux project SUB [ARGS]`

First-level shortcuts to the `cycle.*` and `project.*` handlers. `SUB` is the handler suffix; args are `key=value`.

```bash
$ arqux cycle current
$ arqux cycle create name=CYCLE-17
$ arqux project status
```

### `arqux handlers`

Lists all registered handlers (dotted names `workspace.status`, `blueprint.claim`, …).

```bash
$ arqux handlers | wc -l
115
```

---

## CORTEX

### `arqux validate PATH`

Validates a `.cortex`: `ARQX:artifact` + structure + semantics. Exit 0 passes (warnings allowed), `--strict` turns warnings into failures.

| Flag | Type | Effect |
|---|---|---|
| `--strict` | flag | Fail on warnings too |

```bash
$ arqux validate .arqux/meta-brain.cortex
Validation: PASS
  [WARN] E027_MALFORMED_SECTION: Section $10 title mismatch…
```

### `arqux cortex-verify PATH`

Verifies the SHA-256 integrity seal (and the `HSH` entries of `seal.cortex`).

**Exit codes**: 0 — integrity verified; 1 — tamper detected, `ERR_HASH_MISMATCH`, or missing `$INTEGRITY` header.

```bash
$ arqux cortex-verify .arqux/brain.cortex
OK: .arqux/brain.cortex integrity verified
$ arqux cortex-verify seal.cortex        # after altering an artifact
FAIL: [ERR_HASH_MISMATCH] cycle.cortex: recorded=148f… actual=01ed…   (exit 1)
```

### `arqux cortex-migrate PATH`

Inspects or migrates legacy CORTEX files to CODEC-CORTEX 1.0. Non-mutating preview by default.

| Flag | Type | Effect |
|---|---|---|
| `--apply` | flag | Write changes (default: dry-run) |
| `--no-backup` | flag | Do not keep the atomic backup |

```bash
$ arqux cortex-migrate file.cortex       # preview
[ { "dry_run": true, "status": "preview" } ]
```

### `arqux migrate PATH`

Injects `ARQX:artifact` + contract into a `.cortex`. Idempotent.

| Flag | Type | Effect |
|---|---|---|
| `--level` | integer | **req.** 0=PACKAGE, 1=BEHAVIORAL, 2=SKILL, 3=BRAIN |
| `--name` | text | **req.** Canonical artifact name |
| `--usage` | text | **req.** `state\|skill\|identity\|lesson\|config` |
| `--kind` | text | `native\|inherited\|adapted` |
| `--agent` | text | Agent name (lessons) |
| `--source`, `--upstream-version` | text | External provenance |

```bash
$ arqux migrate doc.cortex --level 3 --name demo --usage state
MIGRATED: doc.cortex
```

### `arqux elevate`

Elevates a lesson to the target level. Dry-run by default; `--apply` writes.

| Flag | Type | Effect |
|---|---|---|
| `--source` | text | **req.** Source container |
| `--target` | text | **req.** Target container/section |
| `--type` | text | **req.** `AXIOM\|LIMIT` (behavioral), `CNST\|CLAIM` (procedural), `KNW` (contextual) |
| `--lesson-id` | text | **req.** Lesson sigil name |
| `--line` | `behavioral\|procedural\|contextual` | Elevation line |
| `--agent` | text | Required for behavioral |
| `--apply` | flag | Apply (default: dry-run) |

```bash
$ arqux elevate --source b.cortex --target b.cortex --type KNW --lesson-id demo
ERROR: Behavioral line only accepts contracts {'LIMIT','AXIOM'}; got 'KNW'
# the default line is behavioral; KNW requires --line contextual
```

### `arqux review --cycle ID`

Renders a cycle to HCORTEX Markdown (human + round-trip). See `docs/en/referencia/formatos.md`.

| Flag | Type | Effect |
|---|---|---|
| `--cycle` | text | **req.** Cycle ID |
| `--path` | text | Project root (default: cwd) |

```bash
$ arqux review --cycle CYCLE-16 > revision.md
# Cycle Review — CYCLE-16 …
```

### `arqux from-hcortex MD_PATH`

Recompiles an HCORTEX report back to `.cortex`. **Exit codes**: 0 — `loss_count == 0`; 1 — errors or loss > 0.

| Flag | Type | Effect |
|---|---|---|
| `--out` | text | Destination `.cortex` (default: `<name>.cortex`) |

```bash
$ arqux from-hcortex revision.md
recompiled revision.cortex entries=2 loss_count=0
```

---

## Evidence and signature

### `arqux evidence export`

Evidence bundle from `.arqux/timelog/SES*.cortex` with a fail-closed privacy gate. Full spec: `docs/en/referencia/formatos.md`.

| Flag | Type | Effect |
|---|---|---|
| `--out` | path | **req.** Destination bundle |
| `--path` | path | Project root (default: cwd) |
| `--redact-private` | flag | Exclude `visibility:"private"` recording the count |
| `--allow-raw` | flag | Include private verbatim (audit; `raw:true`) |

**Exit codes**: 0 — bundle written; 1 — `EXPORT_BLOCKED` (private without flag) or mutually exclusive flags.

```bash
$ arqux evidence export --out b.cortex
EXPORT_BLOCKED: 1 private-marked field(s) found — export blocked.   (exit 1)
$ arqux evidence export --out b.cortex --redact-private
bundle b.cortex spans=1 events=2 redacted=1
```

### `arqux policy keygen KEY_PATH`

Generates an Ed25519 keypair: `seed:` + `public:` hex, `0600` file.

```bash
$ arqux policy keygen emisor.key
key_id:e4178958… created emisor.key
```

### `arqux policy sign DOC --key PATH`

Appends `SIG:signature` to the document (and injects `SIG:sig_contract` into `$0`). **Modifies the file** — work on a copy for demos.

### `arqux policy verify DOC`

Verifies the signature. `--key` optional: without it, resolves `public:` in `.arqux/keys/` next to the document.

**Exit codes**: 0 — `SIGNATURE_VALID`; 1 — `ERR_INVALID_SIGNATURE`, `ERR_NO_SIGNATURE`, `ERR_KEY_MISMATCH`, `ERR_KEY_NOT_FOUND`.

```bash
$ arqux policy verify bundle.cortex --key emisor.key
SIGNATURE_VALID key_id:e4178958…
```

---

## Operations

### `arqux backup`

`.tar.gz` backup of `.arqux/` with timestamp + sibling `.sha256` file, in the current directory.

```bash
$ arqux backup
backup created: arqux-20261115T215719Z.tar.gz (62623 bytes, sha256=c93325d7…)
```

### `arqux restore BACKUP_FILE`

Restores `.arqux/` **to the original path recorded in the backup**; the previous state is preserved as `.arqux.prev`.

```bash
$ arqux restore arqux-20261115T215719Z.tar.gz
restore ok from arqux-20261115T215719Z.tar.gz previous_backup=/tmp/ws/.arqux.prev
```

---

## Sync

### `arqux push-delta`

Applies a policy delta to the authoritative journal. Optimistic locking.

| Flag | Type | Effect |
|---|---|---|
| `--workspace` | text | **req.** Emitting workspace ID |
| `--delta` | path | **req.** `.cortex` with the rules |
| `--base` | integer | **req.** Journal version it was built on |
| `--path` | path | Workspace holding the journal (default: cwd) |

**Exit codes**: 0 — applied; 1 — `ERR_CONFLICT_VERSION` or `ERR_EMPTY_DELTA`.

```bash
$ arqux push-delta --workspace ws-1 --delta d.cortex --base 0
applied delta from ws-1: version=1 rules=1
$ arqux push-delta --workspace ws-1 --delta d.cortex --base 0   # same base, journal already at 1
ERR_CONFLICT_VERSION: journal is at version 1, delta claims base 0   (exit 1)
```

### `arqux pull-policy`

Prints the journal's current policy section.

```bash
$ arqux pull-policy
# journal policy — version 1
RUL:no_raw_private{check:"secret_pattern", action:"deny", …}
```

### `arqux sync-harnesses`

Renders `.arqux/` governance to `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.opencode/instructions.md` with a shared `source_hash`.

| Flag | Type | Effect |
|---|---|---|
| `--path` | text | Project root (default: cwd) |

```bash
$ arqux sync-harnesses
source_hash:0badd4d4…
  wrote AGENTS.md  wrote CLAUDE.md  wrote GEMINI.md  wrote .opencode/instructions.md
```

### `arqux drift-check`

Detects manual edits in the projections. **Exit codes**: 0 — everything matches; 1 — `DRIFT_DETECTED` + diff.

```bash
$ arqux drift-check
OK AGENTS.md
OK CLAUDE.md
OK GEMINI.md
OK .opencode/instructions.md
```

### `arqux loop-watch`

Autonomous-loop watcher: detects stalls, enqueues WAKEs.

| Flag | Type | Effect |
|---|---|---|
| `--path` | text | Project to watch |
| `--interval` | float | Seconds between ticks |
| `--once` | flag | Single tick (testing) |

```bash
$ arqux loop-watch --once
loop-watch tick scanned=0 wakes=[] stalled=[] errors=0
```

---

## Agents and skills

### `arqux wake --identity NAME`

Ultra-dense boot payload for agents: valid cortex:1.0 with registry state, enforce rules and in-flight task.

| Flag | Type | Effect |
|---|---|---|
| `--identity` | text | **req.** Identity/role (see `.arqux/identities/*.cortex`) |
| `--path` | text | Project root (default: cwd) |

```bash
$ arqux wake --identity alfred
$0:format{cortex:1.0, encoding:UTF-8}
IDN:wake{identity:"alfred", kind:"generic", workspace:"…", project:"none", …}
TSK:none{task_id:"none", note:"no in-progress task"}
```

### `arqux identity list` / `arqux identity resolve NAME`

Agent identity inventory and resolution. `--identities-dir` overrides the directory.

```bash
$ arqux identity list
alfred  auditor  executor  governor  heimdall  jarvis  seshat
$ arqux identity resolve alfred
AXM contracts: 7 … LIM contracts: 4 …
```

### `arqux identity elevate`

Injects an `AXM`/`LIM` into an agent's identity.

| Flag | Type | Effect |
|---|---|---|
| `--agent` | text | **req.** Agent name |
| `--lesson-id` | text | **req.** Lesson sigil |
| `--type` | `AXIOM\|LIMIT` | **req.** |
| `--pattern` | text | Rule body |
| `--evidence-ref` | text | Evidence reference |
| `--identities-dir` | text | Alternate directory |

### `arqux skill list` / `arqux skill resolve NAME` / `arqux skill import NAME`

Skills with provenance (`Adapted > Original > Native`). `import` onboards third-party skills.

| Flag (import) | Type | Effect |
|---|---|---|
| `--source` | text | **req.** Upstream URL/path |
| `--content` / `--from-file` | text | Inline content or file |
| `--upstream-version` | text | Version tag |
| `--arqux-root` | text | `.arqux/` root override |

```bash
$ arqux skill list
autonomia        native   adapted  .arqux/skills/autonomia.skill.md
cortex           native   adapted  .arqux/skills/cortex.skill.md
…
```

---

## Services

Long-running processes; they produce no output of their own when started correctly.

### `arqux serve`

MCP server over stdio — the agent's entry point to the handlers.

| Flag | Type | Effect |
|---|---|---|
| `--verbose` | flag | Verbose startup |

### `arqux session-bridge serve`

Host-bridge broker in the foreground — Unix socket between agent sessions.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--socket` | text | `ARQUX_HOST_BRIDGE_SOCKET` or `XDG_RUNTIME_DIR` | Socket path |
| `--request-timeout` | float | 90.0 | Request timeout |

### `arqux serve-plantuml`

PlantUML render server.

| Flag | Type | Effect |
|---|---|---|
| `--port` | integer | Listen port (default 9876) |

### `arqux setup-plantuml`

Installs `plantuml.jar` in `~/.arqux/bin/`. `--force` re-downloads.

### `arqux render-diagram PUML_FILE`

Single `.puml` → image render.

| Flag | Type | Effect |
|---|---|---|
| `--format` | `svg\|png` | Output format |
| `-o`, `--output` | text | Destination directory |

```bash
$ arqux render-diagram diagrams/architecture.puml --format svg -o /tmp
/tmp/architecture.svg
```

---

## Extensions

Optional extras — require `pip install arqux[comms]` / `arqux[voice]`.

### `arqux comms-serve` / `arqux comms-doctor`

The comms extension's MCP server and its diagnostic. `comms-doctor` checks dependencies, token, allowlist and egress — **fail-closed**: with no token and an empty allowlist, it reports failures.

```bash
$ arqux comms-doctor
[PASS] dep:httpx        import ok
[FAIL] telegram:token   MISSING (set ARQUX_COMMS_TELEGRAM_TOKEN)
[FAIL] allowlist        EMPTY (fail-closed: nobody allowed)
[PASS] egress           OFF (default)
2 failure(s)
```

### `arqux voice-serve` / `arqux voice-doctor` / `arqux voice-daemon`

Voice extension. `voice-daemon` manages the persistent daemon:

| Subcommand | Effect |
|---|---|
| `start` | Listen in background. Flags: `--foreground`, `--name`, `--mode solo\|meet`, `--agent`, `--lang`, `--mic` |
| `status` | Daemon and meeting status |
| `stop` | Stop and release devices |
| `restart` | Restart with a fresh session (same flags as `start` minus `--foreground`) |

```bash
$ arqux voice-daemon status          # without the extra installed:
ERROR: voice extra not installed (No module named 'numpy')   (exit 1)
```

**Honest note**: `voice-doctor` without the `arqux[voice]` extra ends in `ModuleNotFoundError: numpy` — a product UX defect (it should report like `voice-daemon`); the way to fix the environment is `pip install arqux[voice]`.

---

## References

- `docs/en/referencia/formatos.md` — artifacts produced by these commands
- `docs/en/guias/evidencia-y-cumplimiento.md` — CISO flow with evidence/policy
- `THREAT_MODEL.md` — security exit codes (`ERR_*`, `PERMISSION_DENIED`)

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
