---
doc_type: canon
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
<p align="center"><sub>Canon · Normative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# ArqUX threat model

English twin of the canonical [`THREAT_MODEL.md`](../../../THREAT_MODEL.md).

Current threat model of ArqUX 1.0.0. Contract with the security evaluator: every claimed control has an implemented mechanism behind it and a command that verifies it; every uncovered threat is declared out-of-scope or residual risk. If a row cannot be executed, the control does not exist — it lives in residuals.

## Scope, actors and assets

**Protected assets**

| Asset | Location | Why it matters |
|---|---|---|
| Governed state | `.arqux/**/*.cortex` (brain, blueprints, journal) | Tampering falsifies the project's operative truth |
| Evidence | timelogs `SES*.cortex`, PULSE (`AUD:*`), `EVD` bundles | Append-only record of who did what; audit base |
| Agent secrets | `.arqux/secrets/<agent>.key` | Compromise = impersonating the agent on HMAC handlers |
| Ed25519 keys | key file outside the workspace (operator path) | Signs bundles and policies; non-repudiation |
| Policy journal | Workspace `journal.cortex` | Authoritative policy shared across clones |

**Threat actors**

| Actor | Capability | Motivation |
|---|---|---|
| Compromised agent process | Invoke MCP handlers, set env vars | Mutate state beyond its role, forge evidence |
| Malicious local user | Read/write filesystem access | Alter `.cortex`, recompute seals, read secrets |
| Insider with governor role | All handlers | Abuse the role, cover tracks |
| Supply-chain attacker | Compromise a PyPI dependency | Execute code inside the agent process |

## Trust boundaries

```
┌─────────────────────────────────────────────────────────┐
│ Agent (external harness — NOT an ArqUX boundary)        │
└──────────────┬──────────────────────────────────────────┘
               │ MCP stdio · JSON-RPC · handler+permission per call
┌──────────────▼──────────────────────────────────────────┐
│ arqux serve                                             │
│  · permissions.py: role→denylist of mutating calls      │
│  · security.py: HMAC agent_id|handler|ts|payload        │
│  · policy_engine.py: enforce rules + secret check       │
└──────────────┬──────────────────────────────────────────┘
               │ atomic write + flock
┌──────────────▼──────────────────────────────────────────┐
│ Filesystem (.arqux/)                                    │
│  · SHA-256 integrity header per .cortex                 │
│  · secrets 0600 · Ed25519 on signed artifacts           │
└─────────────────────────────────────────────────────────┘
```

The real boundary is the MCP call: every access to governed state goes through a handler with a permission check. Transport is stdio — the MCP server opens no network socket.

## Threats and controls

| # | Threat | Control | Real mechanism | Executable verification |
|---|---|---|---|---|
| 1 | Agent impersonation on sensitive handlers | Invocation HMAC signature | `security.py: sign_request/verify_request` — signs `agent_id\|handler\|timestamp\|payload_hash`, `hmac.compare_digest` comparison | `tests/test_security_hmac.py` |
| 2 | Signed-invocation replay | Freshness window | `MAX_CLOCK_SKEW_SECONDS = 300`; larger skew → `IdentityVerificationError` | `tests/test_security_hmac.py` |
| 3 | Auditor runs a mutating handler | Per-mutating-invocation denylist | `permissions.py: _is_mutating_invocation` — auditor denied on mutation, allowed on preview/read; `ROLE_CONTROL_HANDLERS={identity.switch}` | `tests/test_auditor_readonly.py`, `tests/test_permissions.py` |
| 4 | Role escalation without enforcement | Strict mode | `ARQUX_STRICT_ROLES=1` activates the check; `PermissionDenied` → `PERMISSION_DENIED` in CORTEX-OUT | `tests/e2e/test_security_controls.py` |
| 5 | Secret written into an artifact | Pre-write check | `policy_engine.py: _check_secret_pattern` registered in `CODE_CHECKS` — detects secret patterns in content | `tests/e2e/test_security_controls.py` |
| 6 | `.cortex` tampering on disk | SHA-256 integrity seal | `security.py: hash_cortex/inject_hash_header/verify_cortex` — mismatch → `TamperError` | `arqux cortex-verify <file>`; `tests/test_security_cortex.py` |
| 7 | Exported-evidence repudiation | Ed25519 document signature | `signing.py` — pure RFC 8032 Ed25519, no external dependency; signs canonical bytes excluding `SIG:signature` lines; tampering → `ERR_INVALID_SIGNATURE` | `arqux policy keygen` + `sign <doc> --key <k>` + `verify <doc> --key <k>` |
| 8 | ID collision under concurrent writes | File lock | `concurrency.py: file_lock()` — cross-process `fcntl.flock(LOCK_EX)` on POSIX, `TimeoutError` after 10 s | `tests/test_concurrency.py` |
| 9 | Journal overwrite with stale base | Optimistic locking | `journal.py: push_delta` requires `base_version` == current version; rejection → `ERR_CONFLICT_VERSION` for human triage | `tests/test_req_m3.py` |
| 10 | Private-data leak in export | Fail-closed privacy gate | `evidence_export.py: export_bundle` — entries marked `visibility:"private"` never leave the workspace: without `--redact-private` or `--allow-raw` → `PermissionError`; `EVD:bundle` records `redacted`/`raw` | `arqux evidence export --out <f> --redact-private`; `tests/test_req_m3.py` |
| 11 | Agent key readable by third parties | Store permissions | `security.py: save_agent_secret` forces `chmod 0600`; `_load_agent_secret` warns if the mode is more permissive | inspect `.arqux/secrets/` |

## Out of scope

Declared, not implicit. These threats are real but **ArqUX does not cover them**:

| Threat | Why it is out |
|---|---|
| Institutional key management (HSM, KMS, corporate rotation) | `generate_keypair`/`load_keypair` operate on files; custody of the Ed25519 private key is the operator's responsibility |
| Journal network transport | Clone-to-clone sync is delegated to the operator's transport (git, rsync, etc.); ArqUX guarantees detectable conflict (`ERR_CONFLICT_VERSION`), not in-transit confidentiality |
| Compromise of the agent's harness/runtime | ArqUX governs state, not the process invoking it; an agent holding a governor's secret is indistinguishable from the governor |
| Host OS hardening | Users with the same UID or root can read `.arqux/secrets/` and recompute seals; a reasonably trustworthy host is assumed |

## Residual risks

| Residual | Honest status | Available mitigation |
|---|---|---|
| SHA-256 seal coexists with content in the same file | Whoever writes the file recomputes the seal — the seal detects corruption and casual edits, not an adversary with full write access | Ed25519 with private key outside the file: real non-repudiation |
| Default role without enforcement | Without `ARQUX_STRICT_ROLES=1`, the model is legacy (governor bypass) | Export the variable in every serious deployment |
| 5-minute replay window | A captured invocation is replayable within the skew | Reduce `MAX_CLOCK_SKEW_SECONDS`; NTP on agents |
| Lock is intra-process only on Windows | `fcntl` does not exist on Windows; the fallback is `threading.Lock` | Do not run concurrent ArqUX processes on Windows |
| Opaque transitive dependencies | `pip-audit` clean on direct deps; the transitive graph is not frozen | Audit periodically; pin a lockfile in deployments |
| Secret readable by same UID/root | 0600 does not protect against the user itself or privileged processes | OS-level disk encryption, restricted shells |

## How to verify this document

```bash
# .cortex integrity (threat 6)
arqux cortex-verify .arqux/brain.cortex

# Ed25519 signature of an artifact (threat 7)
# `sign` appends the SIG:signature line to the document — work on a copy
arqux policy keygen /tmp/demo.key
cp EVIDENCE.md /tmp/evidence-demo.md
arqux policy sign /tmp/evidence-demo.md --key /tmp/demo.key
arqux policy verify /tmp/evidence-demo.md --key /tmp/demo.key
# → SIGNATURE_VALID (exit 0); any altered byte → ERR_INVALID_SIGNATURE (exit 1)

# Privacy gate on export (threat 10)
arqux evidence export --out /tmp/bundle.cortex --redact-private

# Auditor denial on a mutating handler (threats 3-4)
ARQUX_STRICT_ROLES=1 ARQUX_AGENT_ROLE=auditor arqux serve
# → invoking any mutating handler returns PERMISSION_DENIED

# Full controls suite
uv run pytest tests/test_security.py tests/test_security_hmac.py \
  tests/test_security_cortex.py tests/test_auditor_readonly.py \
  tests/test_permissions.py tests/e2e/test_security_controls.py
```

## What this document is not

- Not an operational compliance guide — that belongs to the CISO evidence guide.
- Not a vulnerability-reporting policy — that is `SECURITY.md`.
- It does not certify third-party controls — every row describes an own, verifiable mechanism, not external services.

## References

- `EVIDENCE.md` — evidence catalog with real fields
- `SECURITY.md` — vulnerability-reporting channel
- `PERMISSIONS.md` — permissions model and enforcement tiers
- `../../es/especificacion/` — normative CORTEX canon

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
