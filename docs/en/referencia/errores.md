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

# Failure contract catalog

*English translation — canonical source: `docs/es/referencia/errores.md`*

Every result code ArqUX 1.0.0 can emit — meaning, typical cause, actionable recovery and the test that covers it. Extracted from the source code (`src/arqux/`); no code was invented. If the code emits a result missing here, this document is stale — report it.

## Output conventions

| Channel | Form | When |
|---|---|---|
| `OUT-ERROR code=<CODE> reason=<text>` | CORTEX-OUT | Handler rejects the invocation — exit 1 via CLI |
| `OUT-WORK` | CORTEX-OUT | Operation applied — exit 0 |
| `Exit codes` | integer | `0` success · `1` functional failure · `2` usage error (click parser) |
| Python exception | `TamperError`, `PermissionDenied`, … | Library surface — the CLI translates it to `OUT-ERROR`/exit≠0 |

Practical rule: an `exit 1` with `ERR_*`/`OUT-ERROR` is a product rejection (read the cause); an `exit 2` is an invocation error (check flags with `--help`).

## Access and identity

| Code | Layer | Meaning | Typical cause | Recovery | Evidence |
|---|---|---|---|---|---|
| `PERMISSION_DENIED` | MCP/CLI | The active role cannot invoke that handler | Auditor invokes a mutating handler; underprivileged role | Export the correct `ARQUX_AGENT_ROLE` or ask the governor for the operation. In legacy mode (no `ARQUX_STRICT_ROLES=1`) the check is lax — do not use lax to dodge a denial | `tests/test_auditor_readonly.py` |
| `PermissionDenied` | library | Base exception — the server translates it to `PERMISSION_DENIED` | Same situation in programmatic use | Catch it and treat as 403 | `src/arqux/permissions.py` |
| `IdentityVerificationError` | library | Invalid HMAC signature or replay outside the window | Wrong secret, `agent_id` mismatch, skew > 300 s | Verify `ARQUX_AGENT_ID`, that `.arqux/secrets/<agent>.key` exists (0600) and that the clock is synced | `src/arqux/security.py`, `tests/test_security_hmac.py` |
| `SESSION_UNBOUND` | handler | Operation requires a bound session and none exists | `context_set` with no open session, or session closed | Open a session with `session.context.set` before operating | session handlers |

## Format and integrity

| Code | Layer | Meaning | Typical cause | Recovery | Evidence |
|---|---|---|---|---|---|
| `TamperError` | library/CLI | The `.cortex` SHA-256 seal does not match its content | Manual edit outside handlers, disk corruption | **Do not recompute the seal by hand.** Restore from `.bak`/`backup` or rewrite via handler; investigate who touched the file | `tests/test_security_cortex.py` |
| `ERR_HASH_MISMATCH` | CLI | `seal.cortex`: artifact differs from the hash recorded at close | Cycle artifact modified post-close | Compare `recorded` vs `actual`; restore the artifact from backup | `tests/test_req_m1.py` |
| `NOT_FOUND` | handler | Nonexistent resource (project, cycle, blueprint, entry) | Typo'd ID, wrong path, resource not created | List first (`*.list`) and verify `path` points at the right project | `src/arqux/server.py` (generic wrapper) |
| `ERR_MISSING_ENFORCE` / `ERR_MISSING_ENFORCE_LEVEL` / `ERR_INVALID_ENFORCE` / `ERR_INVALID_ENFORCE_LEVEL` | policy engine | Malformed policy rule or missing enforce level | `RUL:` rule without a required field or value outside the set | Fix the rule in the delta; `validate_policy_file` diagnoses it before applying | `src/arqux/core/policy_engine.py` |

## Synchrony

| Code | Layer | Meaning | Typical cause | Recovery | Evidence |
|---|---|---|---|---|---|
| `ERR_CONFLICT_VERSION` | CLI/journal | `push-delta` with a stale `base_version` | Another clone applied a delta first | `arqux pull-policy` → rebuild the delta on the current version → retry with new `--base`. Human triage by design: never overwritten | `tests/test_req_m3.py` |
| `ERR_EMPTY_DELTA` | journal | The delta contains no applicable rules | Empty delta file or no `RUL:`/`POL:` entries | Inspect the delta `.cortex` — it must declare rules in its section | `tests/test_req_m3.py` |
| `DRIFT_DETECTED` | CLI | Projection hand-edited (AGENTS/CLAUDE/GEMINI/.opencode) | Direct edit of a generated file | `arqux sync-harnesses` regenerates — the golden rule is *regenerate, do not edit* | `tests/test_req_m2.py` |
| `TimeoutError` | library | `file_lock` not acquired within 10 s | Sibling process holds the lock, or orphan lock | Retry; if persistent, check processes holding the `.lock` sidecar | `src/arqux/concurrency.py` |

## Evidence and signature

| Code | Layer | Meaning | Typical cause | Recovery | Evidence |
|---|---|---|---|---|---|
| `EXPORT_BLOCKED` | CLI | Export with `visibility:"private"` fields without an explicit flag | Timelogs contain private entries | Human decision: `--redact-private` (exclude, count recorded) or `--allow-raw` (include, `raw:true`). No flag, no export — *fail-closed* | `tests/test_req_m3.py::test_export_blocked_without_flags` |
| `SIGNATURE_VALID` | CLI | Ed25519 signature verified — **success, not an error** | `policy verify` succeeded | — | `tests/test_req_m3.py` |
| `ERR_INVALID_SIGNATURE` | CLI | The document was altered or signed by another key | Post-signing tamper, wrong key | Compare the SIG `key_id` with the key used; obtain the intact document again | `tests/test_req_m3.py` |
| `ERR_NO_SIGNATURE` | library | The document contains no `SIG:signature` | `verify` on an unsigned doc | Sign first (`policy sign`) or verify the right file | `src/arqux/signing.py` |
| `ERR_KEY_MISMATCH` | library | The offered public key does not match the signing `key_id` | `--key` points at another keypair | Use the keypair whose `public:` matches the `SIG:signature`'s `key_id:` | `src/arqux/signing.py` |
| `ERR_KEY_NOT_FOUND` | library | No `--key` and no resolvable `public:` in `.arqux/keys/` | Auditor without a public key | Place the emitter's `public:` file under `.arqux/keys/` next to the document | `src/arqux/signing.py` |
| `POLICY_BLOCK` | policy engine | An enforce rule denied the mutation | Evaluate hook with `action:"deny"` (e.g. `secret_pattern`) | Read the blocking rule (`pull-policy`); fix the content, not the rule | `src/arqux/core/policy_engine.py` |

## Platform

| Code | Layer | Meaning | Typical cause | Recovery | Evidence |
|---|---|---|---|---|---|
| `MISSING_DEPENDENCY` | cortex handler | Required dependency absent | codec or module not installed in the environment | `uv sync` / reinstall the corresponding extra | `src/arqux/handlers/cortex/read_write.py` |
| `ENGINE_UNAVAILABLE` | learning handler | Learning engine unavailable | Engine dependency absent | Reinstall `codec-cortex`/project environment | `src/arqux/handlers/cortex/learning.py` |
| `exit 2` | click parser | Usage error: nonexistent flag, missing arg | `--key` omitted, mistyped command | `<cmd> --help` — the `cli.md` reference lists every flag | click convention |

## Generic MCP server rejections

Every handler rejects with `OUT-ERROR code=<CODE>`; besides the domain codes above, the wrapper emits:

| Code | Meaning | Typical cause | Recovery | Evidence |
|---|---|---|---|---|
| `INVALID_ARGS` | Invocation arguments do not satisfy the handler schema | Required field omitted (`task_id`), wrong type | Check `handler.list`/`describe` for the handler — required fields appear in its schema | `src/arqux/server.py` |
| `INTERNAL` / `INTERNAL_ERROR` | Unhandled exception inside the handler | Handler defect or unexpected state | Report as a bug with the invoking payload — do not retry blindly | `src/arqux/constants.py` |
| `VALIDATION` | The read state fails structural validation | `.cortex` with pending E0xx diagnostics | Run `arqux validate` on the artifact and resolve each diagnostic | `src/arqux/server.py` |

## Validation diagnostics (`arqux validate` / `cortex.verify`)

`validate` emits severity-ranked diagnostics — explicit model in `src/arqux/constants.py`: only `severity:"error"` invalidates the document (`E0xx`); `W0xx` are deduplicated warnings that never invalidate; `I0xx` is informational.

| Code | Severity | Meaning | Recovery | Evidence |
|---|---|---|---|---|
| `E024_LEVEL3_MISSING_FOCUS` | error | Level-3 brain without an active `FCS:` | Add an `FCS:` entry with current status | `constants.py`, `validators/brain_semantics.py` |
| `E026_MISSING_SECTION` | error | Canonical brain section absent | Restore the missing section (`$0`–`$10` GRADIENT-12 canon) | `validators/brain_structure.py` |
| `E027_MALFORMED_SECTION` | error | Section title does not match canon (e.g. `REGISTRY` where `SESSIONS` expected) | Rename the section to the canonical title from `BRAIN_SECTION_TITLES` | `validators/brain_structure.py` — observed in real `arqux validate` |
| `E028_NO_ACTIVE_OBJECTIVES` | error | Brain with no `OBJ:` in current state | Declare an active objective or archive the brain | `constants.py` |
| `W001_NO_METADATA` | warning | `.cortex` without `ARQX:artifact` → degrades to LEVEL 0 | Add an `ARQX:artifact{...}` entry | `constants.py` |
| `W002_INCOMPLETE_BRAIN` | warning | Brain with fewer than 8 active sections | Complete canonical sections or accept a reduced brain | `validators/brain_structure.py` |
| `W003_LEARNING_DEBT_BEHAVIORAL` | warning | Expired behavioral lesson | Revalidate or retire the lesson | `constants.py` |
| `W004_STALE_INHERITED_SKILL` | warning | Inherited skill stale vs upstream | Re-sync the skill | `constants.py` |
| `W005_MISSING_ORIGINAL_REF` | warning | Adapted entry without `original_ref` | Add the source reference | `constants.py` |
| `I001_CODEC_BACKEND_INFO` | info | Which codec backend produced the validation | — | `constants.py` |
| `I002_PLACEHOLDER_VALUE` | info | Values with `<placeholder>` marker pending | Fill in the pending values | `constants.py` |
| `I003_EMPTY_SECTION` | info | Section declared with zero entries | Populate or remove the section | `constants.py` |

### Codec and policy diagnostics (`E0xx`/`W0xx` prefix)

The CORTEX codec (`codec-cortex`, required dependency) and the `core/state` validators emit additional format and governance diagnostics; the most frequent on the surface:

| Code | Origin | Meaning | Recovery |
|---|---|---|---|
| `E002_GLOSSARY_NOT_FIRST` | codec | The `$0` glossary is not the first section | Reorder sections — the glossary is canonical `$0` |
| `E003_UNKNOWN_SIGIL` | codec | Sigil used but not declared in glossary | Declare the sigil or fix the typo |
| `E007_ATTRS_POS_CONTRACT_MISSING` / `E027_ATTRS_POS_ARITY` | codec | Attrs position contract missing/invalid arity | Declare the contract `fields:` correctly |
| `E008_DUPLICATE_ENTRY` | codec | Repeated entry in section | Remove the duplicate — check write handlers |
| `E015_ATOMIC_WRITE_FAILED` | codec | Atomic write failed | Retry; check filesystem/locks |
| `E023_LEVEL1_LIVE_STATE` | ArqUX `core/state` | Live state (WRK/FCS/LNG-runtime) in a level-1 artifact (identity) — unless a curated exemption | Move live state to a level-3 brain |
| `E025_INVALID_SURVIVE` | ArqUX `core/state` | `survive:` field outside the allowed set | Correct the survive value |
| `E031_SECRET_NOT_BYPASSABLE` | policy | Attempted bypass of a secret rule | Not recoverable by design — content cannot contain secrets |
| `E032_CRITICAL_SIGIL_INCOMPLETE` / `E033_ZERO_SECTION_MEMORY_ENTRY` / `E034_CRITICAL_REQUIRED_FIELD_EMPTY` | ArqUX `core/state` | Incomplete critical sigil, zero-section memory, empty required field | Complete the flagged fields/sections |

The canonical enumeration lives in the source: `src/arqux/constants.py` (E024–E028, W0xx, I0xx), `src/arqux/validators/` (emission) and the `codec-cortex` package (format diagnostics). `arqux validate` is the surface where they all emerge together.

## Uncoded errors — honesty

Not every failure carries a symbolic code. Native exceptions (`FileNotFoundError`, OS `PermissionError`, `ValueError`) can surface from unwrapped paths — emerging as a CLI traceback or generic MCP `OUT-ERROR`. Treat them as a surface bug: if a recurring error lacks a code, it is a formalization candidate, not something to silence.

## References

- `docs/en/referencia/cli.md` — exit codes per command
- `docs/en/referencia/formatos.md` — artifacts whose verification emits these codes
- `THREAT_MODEL.md` — threat model behind the security `ERR_*` codes

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
