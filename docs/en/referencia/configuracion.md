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

# ArqUX configuration

*English translation — canonical source: `docs/es/referencia/configuracion.md`*

The complete configurable surface in one place: environment variables, file paths, required permissions, operational defaults and per-scenario profiles. Every entry cites where it is consumed in `src/` — the document audits with `grep`.

## Environment variables — core

Variables that `src/arqux` code reads via `os.environ`. The prefix is configurable with `ARQUX_ENV_PREFIX` (reads use `{prefix}VAR`).

| Variable | Values | Default | Effect | Consumed by |
|---|---|---|---|---|
| `ARQUX_AGENT_ID` | text | `anonymous` | Agent identity for HMAC signing and role resolution | `security.py`, `permissions.py` |
| `ARQUX_AGENT_SECRET` | secret | empty | Shared HMAC key — without it authentication fails closed (`IdentityVerificationError`) | `security.py` |
| `ARQUX_AGENT_ROLE` | `governor`/`auditor`/`executor` | `governor` | Role applied in legacy mode (no session); in strict mode the role comes from the session | `permissions.py` |
| `ARQUX_AGENT_SIGNATURE` | hex HMAC | — | Invocation signature in legacy mode | `permissions.py` |
| `ARQUX_AGENT_TIMESTAMP` | epoch | — | Signed timestamp — outside ±300 s is rejected | `permissions.py`, `security.py` |
| `ARQUX_PROJECT` | text | — | Project bound to the legacy credential | `permissions.py` |
| `ARQUX_STRICT_SECURITY` | `0`/`1` | `0` | Strict security mode: full signature/role enforcement | `security.py`, `permissions.py` |
| `ARQUX_STRICT_ROLES` | `0`/`1` | `0` | Mutating-handler denylist applied per role (auditor → read-only) | `permissions.py` |
| `ARQUX_EXECUTION_KEY` | text | — | Execution key the transport/host sets for correlation | `execution.py` |
| `ARQUX_STRICT_EXECUTION` | `0`/`1` | `0` | `1` disables the per-process implicit key — demands an explicit key | `execution.py` |
| `ARQUX_ALLOW_IMPLICIT_EXECUTION` | `0`/`1` | `0` | `1` allows the per-process implicit key (fallback) | `execution.py` |
| `ARQUX_ENV_PREFIX` | text | `ARQUX_` | Changes the prefix used to read all the variables above | `constants.py` |
| `ARQUX_SUSPENDED` | `0`/`1` | — | Suspends mutations via protocol handlers (set/read by the handler itself) | `handlers/protocol.py` |
| `ARQUX_HOST_BRIDGE_SOCKET` | path | `$XDG_RUNTIME_DIR` | Host bridge socket for alternate transport | `host_bridge.py` |

### Extension variables

**Comms** (`arqux[comms]` — fail-closed by design):

| Variable | Default | Effect | Consumed by |
|---|---|---|---|
| `ARQUX_COMMS_EGRESS` | `off` | Egress gate — without `on` there is no egress | comms module |
| `ARQUX_COMMS_ALLOWLIST` | empty | Allowed destination list (empty = all blocked) | comms module |
| `ARQUX_COMMS_TELEGRAM_TOKEN` | — | Telegram bot token | comms module |

**Voice** (`arqux[voice]` — optional extra). Defaults live in `src/arqux/voice/config.py`; requires `numpy` and the extra's dependencies — without them `voice-doctor` fails with `ModuleNotFoundError`.

| Variable | Effect |
|---|---|
| `ARQUX_VOICE_ENGINE` | Selected voice engine |
| `ARQUX_VOICE_MODELS` | Model path/manifest |
| `ARQUX_VOICE_TTS` | TTS engine |
| `ARQUX_VOICE_ENDPOINT` | Voice service endpoint |
| `ARQUX_VOICE_MIC` | PipeWire input selector (same as `--mic`) |
| `ARQUX_VOICE_SINK` | Output device |
| `ARQUX_VOICE_MEETINGS` | Meetings-mode configuration |
| `ARQUX_VOICE_DAEMON` | Daemon context flag |
| `ARQUX_VOICE_DAEMON_LOG` / `ARQUX_VOICE_DAEMON_PID` / `ARQUX_VOICE_DAEMON_SOCKET` | Daemon paths (log, pidfile, socket) |
| `ARQUX_VOICE_AUTO_RECOVER` | Daemon auto-recovery |
| `ARQUX_VOICE_CHUNK_MS` | Audio chunk size (default `64` in config) |
| `ARQUX_VOICE_BARGE_GRACE_MS` / `ARQUX_VOICE_BARGE_MIN_FRAMES` / `ARQUX_VOICE_BARGE_MIN_RMS` | Barge-in thresholds (grace, min frames, min RMS) |
| `ARQUX_VOICE_RSS_BUDGET_MB` | RSS memory budget |
| `ARQUX_VOICE_AGENT_ENDPOINT` / `ARQUX_VOICE_AGENT_MODEL` / `ARQUX_VOICE_AGENT_API_KEY` / `ARQUX_VOICE_AGENT_COMMAND` / `ARQUX_VOICE_AGENT_SYSTEM` / `ARQUX_VOICE_AGENT_TIMEOUT` / `ARQUX_VOICE_AGENT_BACKEND` | Agent backend configuration for meet mode (`agent_backend.py`) |

### Test-only variable

`BENCHMARK_PUBLISH` appears in `tests/` (benchmark publishing), not in `src/` — it is not a product configuration; documented here so the operator does not look for it at runtime.

### Names that look like variables but are internal constants

`ARQUX_VERSION`, `ARQUX_DIR`, `ARQUX_FORMAT_DECL`, `ARQUX_GLOSSARY_TEXT`, `ARQUX_METADATA`, `ARQUX_META_SECTION`, `ARQUX_META_TITLE`, `ARQUX_META_SIGIL`, `ARQUX_META_ENTRY`, `ARQUX_META_PRIORITY` — Python constants in `constants.py`/`formats.py`. **Not environment-configurable** — documented to prevent grep confusion.

## Filesystem paths

| Path | Content | Permissions | Version? |
|---|---|---|---|
| `<project>/.arqux/` | Project governance | — | Yes (except below) |
| `.arqux/brain.cortex` | Level-3 brain — governed memory | conventional | Yes |
| `.arqux/secrets/<agent>.key` | Per-agent HMAC key | **0600 mandatory** — `security.py` enforces it | **Never** — symmetric secret |
| `.arqux/keys/` | Ed25519 keypairs (`seed:` + `public:`) | **0600** when created by `policy keygen` | `public:` shareable; `seed:` **never** |
| `.arqux/journal.cortex` | Authoritative policy journal | conventional | Yes — it is history |
| `.arqux/timelog/SES*.cortex` | Per-session timelogs | conventional | Yes — evidence |
| `.arqux/handoffs/`, `cycles/`, `blueprints/` | Cycle artifacts | conventional | Yes |
| `<workspace>/.arqux/meta-brain.cortex` | Workspace meta-brain | conventional | No — local workspace state |
| `<workspace>/.arqux/identities/*.cortex` | Identity contracts | conventional | No — they live in the workspace |
| `AGENTS.md` `CLAUDE.md` `GEMINI.md` `.opencode/instructions.md` | Governance projections | generated | Regenerated by `sync-harnesses` — do not hand-edit |
| `$XDG_RUNTIME_DIR/arqux-*` | Bridge/daemon sockets | runtime | No |

## Operational defaults (verified in code)

| Parameter | Value | Location |
|---|---|---|
| HMAC skew window | **300 s** (±5 min) | `security.py` — `MAX_CLOCK_SKEW_SECONDS` |
| `fcntl.flock` timeout | **10 s** | `concurrency.py` |
| `session-bridge --request-timeout` | **90.0 s** | `cli.py` |
| `secrets/*.key` permission | **0600** enforced | `security.py` |
| Ed25519 keypair permission | **0600** at keygen | `signing.py` — verified in execution |

## Per-scenario profiles

| Profile | Minimum configuration | Notes |
|---|---|---|
| Local development | No env vars — lax mode by default | Roles are lax without `STRICT_ROLES`/`STRICT_SECURITY`; comfortable for iterating |
| Governed production | `ARQUX_AGENT_ID` + `ARQUX_AGENT_SECRET` + `ARQUX_STRICT_SECURITY=1` + `ARQUX_STRICT_ROLES=1` + `secrets/` 0600 | Role denylist active; auditor stays read-only (`PERMISSION_DENIED` verified live) |
| Air-gapped | Same as production; no network access | The whole core operates offline: init, MCP stdio, pure Ed25519 signatures (no external libs — `signing.py` is pure-python by design). Verified: `uv run arqux init/status/validate/policy` work without connectivity. Voice/comms extras require their dependencies pre-installed |
| CI | `ARQUX_AGENT_ID=ci` + pipeline secret | The docs/`validate`/`doctor` commands are non-interactive and pipeline-usable |

## Per-path security rules

- `secrets/` and keypair `seed:` → mandatory `.gitignore`; the product enforces 0600 but does not prevent commit — the barrier is the operator's.
- `visibility:"private"` fields in timelogs → `EXPORT_BLOCKED` gate on export (see `errores.md`).
- Harness projections (AGENTS/CLAUDE/GEMINI) are conceptually read-only: `drift-check` flags manual edits as `DRIFT_DETECTED`.

## References

- `docs/en/referencia/cli.md` — flags per command (not repeated here)
- `docs/en/referencia/errores.md` — codes these paths/variables produce on failure
- `THREAT_MODEL.md` — justification for each control
- `docs/en/guias/evidencia-y-cumplimiento.md` — key and bundle handling

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
