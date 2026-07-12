# Threat Model

> **Document version:** 1.0 (2026-07-12)
> **ArqUX version:** 0.4.3+

This document describes the threat model for ArqUX, including the attack surface, threat agents, attack vectors, and mitigations.

---

## 1. Attack Surface

ArqUX exposes the following attack surfaces:

| Surface | Description | Trust Level |
|---------|-------------|-------------|
| **CLI** | `arqux` command-line tool | Local user (trusted) |
| **MCP Server (stdio)** | `arqux serve` on stdio | Local agent process (semi-trusted) |
| **MCP Server (SSE)** | `arqux serve` over HTTP (planned) | Network (untrusted) |
| **PlantUML Server** | `arqux serve-plantuml` on port 9876 | Local network (semi-trusted) |
| **`.arqux/` directory** | Filesystem state | Local filesystem (trust depends on host) |
| **`.arqux/secrets/`** | HMAC secret keys | Local filesystem (must be 0600) |
| **Environment variables** | `ARQUX_AGENT_ID`, `ARQUX_AGENT_ROLE`, etc. | Process environment (trusted) |
| **PyPI package** | `pip install arqux` | Public supply chain |

---

## 2. Threat Agents

| Agent | Motivation | Capability |
|-------|------------|------------|
| **Compromised agent process** | Escalate privileges, mutate state outside role | Can set env vars, call handlers |
| **Malicious local user** | Tamper with `.cortex` files, forge evidence | Full filesystem access to `.arqux/` |
| **Network attacker (SSE)** | Inject malformed MCP requests, replay attacks | Network access to MCP server |
| **Supply chain attacker** | Inject malicious code via dependencies | Compromise PyPI or transitive deps |
| **Insider with governor access** | Abuse governor role, cover tracks | Full handler access |

---

## 3. Attack Vectors and Mitigations

### 3.1 Identity Bypass (CRÍTICO-1)

**Vector:** An agent claims to be another agent (e.g. claims `agent_id=alfred` while actually being `jarvis`) to perform governor-only actions.

**Mitigation:**
- HMAC-SHA256 signature verification for `HMAC_REQUIRED` handlers (`identity.record`, `evidence.record`, `blueprint.approve`, `blueprint.re_delegate`)
- Signature binds `agent_id | handler | timestamp | payload_hash` — prevents substitution
- `MAX_CLOCK_SKEW_SECONDS = 300` prevents replay attacks
- `hmac.compare_digest` for constant-time comparison (prevents timing attacks)
- Strict mode (`ARQUX_STRICT_SECURITY=1`) rejects unverified requests

**Residual risk:** If an attacker compromises `.arqux/secrets/<agent>.key`, they can sign requests as that agent. Mitigation: file permissions 0600, regular rotation, OS-level disk encryption.

### 3.2 Evidence Tampering (CRÍTICO-2)

**Vector:** An attacker modifies a `.cortex` file to alter or remove evidence entries.

**Mitigation:**
- SHA-256 `$INTEGRITY` header at the top of every `.cortex` file
- `verify_cortex()` recomputes the hash and compares — raises `TamperError` on mismatch
- Auto-signing is NOT applied on write; integrity is verified on demand via `arqux cortex-verify` (P1-P / P1-Q reconciliation — see BLP-014)
- `arqux cortex-verify <path>` CLI for manual verification
- CI step (planned) verifies all `.cortex` files on every commit

**Residual risk:** Hash is stored in the same file as content. An attacker who can modify the file can also recompute the hash. Mitigation: Ed25519 signing (`sign_cortex` / `verify_cortex_signature`) with external private key provides non-repudiation. For pilot, file-level integrity is sufficient.

### 3.3 Permission Escalation (P0-B)

**Vector:** An auditor-role agent calls a mutating handler (e.g. `blueprint.cancel`) to destroy state.

**Mitigation:**
- `MUTATING_HANDLERS` frozenset (P0-B) — auditor is denied all 50+ mutating handlers
- Strict mode (`ARQUX_STRICT_ROLES=1`) required for enforcement
- Tests in `tests/test_auditor_readonly.py` validate 30+ scenarios

**Residual risk:** None in strict mode. In legacy mode (default), all roles have governor-like access — this is documented as "not for production".

### 3.4 Replay Attack

**Vector:** An attacker captures a signed request and replays it later.

**Mitigation:**
- HMAC signature includes `timestamp` field
- `verify_request` checks `abs(now - timestamp) > MAX_CLOCK_SKEW_SECONDS` → `IdentityVerificationError`
- Clock skew window: 5 minutes (configurable)

**Residual risk:** Within the 5-minute window, a replayed request is accepted. Mitigation: agents must be NTP-synced; for high-assurance scenarios, reduce `MAX_CLOCK_SKEW_SECONDS`.

### 3.5 Secret Store Traversal

**Vector:** An attacker with read access to `.arqux/secrets/` reads all agent keys.

**Mitigation:**
- Secret files are mode 0600 (owner read/write only)
- `save_agent_secret` enforces 0600 via `chmod`
- `_load_agent_secret` warns if mode > 0600
- `.gitignore` excludes `.arqux/secrets/` (NEVER commit)

**Residual risk:** Local user with `root` or same-UID access can read secrets. Mitigation: OS-level disk encryption, restricted shell access, regular rotation.

### 3.6 Race Condition in ID Generation (ALTO-2)

**Vector:** Two concurrent `blueprint.create` calls generate the same BLP-NNN ID, causing one to overwrite the other.

**Mitigation:**
- `concurrency.file_lock()` uses `fcntl.flock(LOCK_EX)` on POSIX — cross-process safe
- `next_blueprint_id_safe()`, `next_task_id_safe()`, `next_cycle_id_safe()` all acquire lock before scanning directory
- Lock timeout: 10 seconds → `TimeoutError` if not acquired

**Residual risk:** On Windows, only in-process locking (`threading.Lock`) — cross-process race possible. Mitigation: do not run multiple ArqUX processes on Windows in pilot.

### 3.7 Sync Brain Silent Failure (P0-A)

**Vector:** `sync_brain` fails silently, meta-brain never reflects workspace metrics, dashboard shows stale data.

**Mitigation:**
- P0-A fix: `init_workspace` now copies meta-brain.cortex template directly (preserves `$2/DOM:arqux`)
- Regression test `test_sync_brain_with_metrics_does_not_warn` fails if ERROR logged
- CI step validates `grep -q "DOM:arqux" /tmp/test-ws/.arqux/meta-brain.cortex`

**Residual risk:** None after fix. Pre-fix, the bug was silent (swallowed by `except Exception`).

### 3.8 CI Bypass (P0-C)

**Vector:** CI workflow triggers on `main` branch but repo uses `master` — CI never runs, regressions ship to PyPI undetected.

**Mitigation:**
- P0-C fix: CI triggers on `[master, main]`
- CI step validates `arqux init`, handlers count, AGENTS.md hash, P0-B regression

**Residual risk:** None after fix. Pre-fix, any regression could ship.

### 3.9 Supply Chain Attack

**Vector:** A compromised dependency (e.g. `codec-cortex`, `mcp`, `pydantic`) injects malicious code.

**Mitigation:**
- `pip-audit --strict` runs clean (no known CVEs)
- Dependencies pinned to `>=` minimum versions (could be tighter)
- `uv.lock` should be committed (P2-13 — currently in `.gitignore`)
- No `pip install` from arbitrary URLs in `pyproject.toml`

**Residual risk:** Transitive dependencies (`ast-serialize`, `librt` from `codec-cortex`) are opaque. Mitigation: enable Dependabot, run `pip-audit` in CI (planned).

### 3.10 PlantUML Server RCE

**Vector:** The PlantUML server (`arqux serve-plantuml` on port 9876) accepts arbitrary PlantUML input, which can include `!include` directives that read local files.

**Mitigation:**
- PlantUML server binds to `localhost` by default
- PlantUML has built-in `!include` restrictions (only files in allowlist)
- Do NOT expose PlantUML server to untrusted networks

**Residual risk:** If exposed to network, an attacker could potentially read local files via `!include`. Mitigation: bind to `127.0.0.1`, firewall port 9876.

---

## 4. Severity Matrix

| Threat | Severity | Likelihood | Impact | Mitigation Status |
|--------|----------|------------|--------|-------------------|
| Identity Bypass | CRITICAL | Low (requires secret compromise) | High (full impersonation) | ✅ Mitigated (HMAC) |
| Evidence Tampering | CRITICAL | Medium (filesystem access) | High (audit integrity) | ✅ Mitigated (SHA-256 + Ed25519) |
| Permission Escalation | CRITICAL | Low (requires strict mode off) | High (auditor mutates state) | ✅ Mitigated (P0-B) |
| Replay Attack | HIGH | Medium (network access) | Medium (single request replay) | ✅ Mitigated (timestamp) |
| Secret Traversal | HIGH | Low (requires filesystem access) | High (all agents compromised) | ✅ Mitigated (0600 + gitignore) |
| Race Condition | MEDIUM | Medium (concurrent agents) | Medium (ID collision) | ✅ Mitigated (fcntl) |
| Sync Brain Silent | MEDIUM | High (was default) | Medium (stale dashboard) | ✅ Mitigated (P0-A) |
| CI Bypass | HIGH | High (was default) | High (regressions ship) | ✅ Mitigated (P0-C) |
| Supply Chain | MEDIUM | Low (PyPI compromise) | High (RCE) | ⚠️ Partial (pip-audit clean, no SBOM) |
| PlantUML RCE | MEDIUM | Low (localhost only) | High (file read) | ⚠️ Partial (bind to localhost) |

---

## 5. Security Best Practices (pilot)

1. **Always** set `ARQUX_STRICT_ROLES=1` and `ARQUX_STRICT_SECURITY=1`
2. **Always** store secrets in `.arqux/secrets/` with mode 0600
3. **Never** commit `.arqux/secrets/` to VCS
4. **Never** disable strict mode to work around a permission issue
5. **Rotate** agent secrets monthly
6. **Verify** `.cortex` integrity regularly with `arqux cortex-verify`
7. **Backup** daily with `arqux backup`
8. **Test** restore quarterly
9. **Monitor** `evidence.list` weekly for unexpected entries
10. **Run** `arqux doctor --fix` weekly

---

## 6. References

- [SECURITY.md](SECURITY.md) — security policy and disclosure SLA
- [PERMISSIONS.md](PERMISSIONS.md) — permissions model
- [PILOT_MODE.md](PILOT_MODE.md) — pilot deployment guide
- [architecture/diagrams/](docs/architecture/diagrams/) — PUML diagrams
