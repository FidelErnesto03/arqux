# Pilot Mode Guide

> **Status:** Required reading before deploying ArqUX in any pilot environment.

This document describes how to deploy ArqUX in a controlled pilot, the configuration required, known limitations, exit criteria, and monitoring obligations.

---

## 1. Pre-Pilot Checklist

Before deploying ArqUX in a pilot environment, verify:

- [ ] **ArqUX version**: `>= 0.4.3` (run `arqux --version`)
- [ ] **Python**: `>= 3.10` (3.12 recommended)
- [ ] **codec-cortex**: `>= 0.5.2` (auto-installed as dependency; required for BLP-041 `$0.1` schema support — see CYCLE-07 T-002)
- [ ] **Strict mode**: `ARQUX_STRICT_ROLES=1` and `ARQUX_STRICT_SECURITY=1` set in environment
- [ ] **Secrets**: `.arqux/secrets/` directory created with one `<agent>.key` file per agent identity (mode 0600)
- [ ] **Identities**: At least one governor identity bound (`arqux identity resolve alfred`)
- [ ] **Workspace**: `arqux init` executed in the workspace root
- [ ] **Project**: At least one project initialized (`arqux call project.init name=<pilot-project>`)
- [ ] **CI**: GitHub Actions workflow runs green on `master` branch
- [ ] **Backup**: `arqux backup` scheduled (cron or manual) at least daily

---

## 2. Configuration

### 2.1 Environment Variables (MANDATORY for pilot)

```bash
# Strict role enforcement — never run pilot without this
export ARQUX_STRICT_ROLES=1

# Strict HMAC enforcement — never run pilot without this
export ARQUX_STRICT_SECURITY=1

# Active agent identity (set per-session)
export ARQUX_AGENT_ID=alfred
export ARQUX_AGENT_ROLE=governor

# HMAC signature (set per-request for HMAC_REQUIRED handlers)
export ARQUX_AGENT_SIGNATURE=<hex-hmac-signature>
export ARQUX_AGENT_TIMESTAMP=<unix-timestamp>

# Optional: agent secret (alternative to .arqux/secrets/<agent>.key)
# export ARQUX_AGENT_SECRET=<hex-secret>
```

### 2.2 Directory Layout (pilot workspace)

```
pilot-workspace/
├── AGENTS.md                          # Installed by arqux init
├── .arqux/
│   ├── meta-brain.cortex              # Cross-project knowledge (integrity verified on demand via arqux cortex-verify)
│   ├── projects.cortex                # Projects index
│   ├── learn-policies.cortex          # Learning engine policies
│   ├── identities/                    # Agent identity contracts
│   │   ├── alfred.cortex              # Governor
│   │   ├── jarvis.cortex              # Executor
│   │   └── heimdall.cortex            # Auditor
│   ├── secrets/                       # HMAC secrets (mode 0600, NEVER commit)
│   │   ├── alfred.key
│   │   ├── jarvis.key
│   │   └── heimdall.key
│   ├── skills/
│   │   ├── *.skill.md
│   │   ├── originals/
│   │   └── workflows/
│   ├── templates/
│   └── packages/
├── project-alpha/                     # Pilot project 1
│   └── .arqux/
│       ├── brain.cortex
│       └── cycles/
│           └── CYCLE-01/
└── project-beta/                      # Pilot project 2
    └── .arqux/
```

### 2.3 Agent Roster (pilot)

| Agent | Role | Identity File | Secret File | Purpose |
|-------|------|---------------|-------------|---------|
| alfred | GOVERNOR | `identities/alfred.cortex` | `secrets/alfred.key` | Creates cycles, assigns, approves, closes |
| jarvis | EXECUTOR | `identities/jarvis.cortex` | `secrets/jarvis.key` | Claims tasks, updates progress, completes |
| heimdall | AUDITOR | `identities/heimdall.cortex` | `secrets/heimdall.key` | Read-only audit, verifies evidence, cannot mutate state |

---

## 3. Known Limitations (pilot scope)

The following are known limitations of ArqUX in pilot mode:

### 3.1 Security

- **Single-tenant only**: no SSO/OIDC integration (planned for v0.5.0)
- **No encrypted secrets at rest**: secrets are stored as plaintext in `.arqux/secrets/<agent>.key` (mode 0600). Use OS-level disk encryption.
- **No secret rotation CLI**: rotation is manual (`generate_secret()` + `save_agent_secret()`)
- **HMAC clock skew**: 5-minute window (`MAX_CLOCK_SKEW_SECONDS`). Agents must be NTP-synced.

### 3.2 Concurrency

- **Cross-process locking** works on POSIX (Linux/macOS) via `fcntl.flock`.
- **Windows**: only in-process locking via `threading.Lock` — do not run multiple ArqUX processes on Windows in pilot.
- **No distributed locking**: pilot assumes single-host deployment.

### 3.3 Performance

- **Cold start**: `arqux init` takes ~200ms (acceptable for pilot)
- **Handler dispatch**: ~200ms per `arqux call` (acceptable for pilot)
- **Test suite**: 18-20 seconds (acceptable for CI)
- **Not benchmarked for >1000 handlers/day**: pilot only.

### 3.4 Auditability

- **File-level tamper detection**: works (SHA-256 $INTEGRITY header)
- **Entry-level tamper detection**: NOT implemented (planned for v0.5.0)
- **Evidence records `actor` and `task/blueprint`**: yes
- **Evidence records `role` and `ts`**: NOT yet (planned for v0.5.0)
- **Evidence records payload hash**: NOT yet (planned for v0.5.0)

### 3.5 Compatibility

- **Python 3.10, 3.11, 3.12**: tested in CI
- **Python 3.13**: NOT tested
- **Linux**: tested
- **macOS**: NOT tested in CI, should work (POSIX)
- **Windows**: NOT tested, partial support (no cross-process locking)

---

## 4. Monitoring

### 4.1 Daily checks

- [ ] `arqux doctor` runs clean (no `fail` status)
- [ ] `.arqux/secrets/*.key` permissions are 0600 (`ls -la .arqux/secrets/`)
- [ ] No `.bak` files in `.arqux/` (run `arqux doctor --fix` if any)
- [ ] `arqux cortex-verify .arqux/meta-brain.cortex` passes
- [ ] `arqux cortex-verify .arqux/brain.cortex` passes (per project)

### 4.2 Weekly checks

- [ ] `arqux backup` runs successfully (`.tar.gz` + `.sha256` created)
- [ ] Test restore on a copy: `arqux restore <backup-file>` in a sandbox
- [ ] Review `evidence.list` for unexpected entries
- [ ] Review `agents.cortex` for unexpected role changes
- [ ] Check CI is green on `master` branch
- [ ] Review `blueprint.list status=blocked` for stuck blueprints

### 4.3 Monthly checks

- [ ] Rotate agent secrets (manual: `generate_secret()` + `save_agent_secret()`)
- [ ] Review `cycle.list` for cycles that should be closed
- [ ] Run `arqux doctor --fix` to clean up any new `.bak` files
- [ ] Audit `.arqux/cycles/*/pulse.jsonl` sizes — rotate if > 10MB

### 4.4 Metrics to collect

| Metric | Source | Target |
|--------|--------|--------|
| Handlers invoked per day | `evidence.list` count grouped by day | Track trend |
| Blueprints completed per cycle | `blueprint.list status=done` count | Track trend |
| Average cycle duration | `cycle.list` + manual timestamps | Decreasing |
| Evidence entries per agent | `evidence.list` grouped by agent | Balanced |
| Tamper detection failures | `arqux cortex-verify` exit codes | 0 |
| CI failures per week | GitHub Actions | 0 |

---

## 5. Exit Criteria (pilot → production)

The pilot is considered successful and ready for production promotion when ALL of the following are true:

### 5.1 Stability

- [ ] **30 consecutive days** with zero `P0` or `P1` issues detected
- [ ] **Zero** `TamperError` exceptions in production logs
- [ ] **Zero** `PermissionDenied` exceptions for legitimate operations
- [ ] **Zero** `sync_brain` ERROR log entries
- [ ] CI green for 30 consecutive days on `master`

### 5.2 Coverage

- [ ] Test coverage `>= 75%` (current: 69%, target after patch: 75%)
- [ ] `security.py` coverage `>= 90%` (current: 89%)
- [ ] `permissions.py` coverage `>= 90%` (current: 86%)
- [ ] No module with `0%` coverage in production code paths

### 5.3 Operational maturity

- [ ] Backup/restore drill completed successfully
- [ ] At least 2 agents of each role (governor, executor, auditor) have operated
- [ ] At least 5 cycles completed end-to-end
- [ ] At least 20 blueprints completed end-to-end
- [ ] At least 1 incident postmortem documented

### 5.4 Documentation

- [ ] `PILOT_MODE.md` (this document) reviewed and updated
- [ ] `SECURITY.md` reviewed by security team
- [ ] `THREAT_MODEL.md` reviewed by security team
- [ ] `ARCHITECTURE.md` reviewed by engineering team
- [ ] Runbook for common incidents documented

---

## 6. Rollback Procedure

If the pilot needs to be rolled back:

1. **Stop all agents** — kill any process with `ARQUX_AGENT_ID` set
2. **Backup current state** — `arqux backup`
3. **Verify backup** — `arqux cortex-verify` on all `.cortex` files
4. **Export evidence** — `arqux call evidence.list` → save output
5. **Remove ArqUX** — `pip uninstall arqux` (keep `.arqux/` directory for audit)
6. **Document reason** — file an incident report explaining the rollback

---

## 7. Incident Response

### 7.1 Tamper detection

If `arqux cortex-verify` reports a tamper:

1. **Immediate**: stop all agents
2. **Preserve evidence**: copy the tampered `.cortex` file to a safe location
3. **Investigate**: check `evidence.list` for the last legitimate mutation
4. **Restore**: `arqux restore <most-recent-backup>`
5. **Audit**: review all agent actions since the last verified backup
6. **Document**: file an incident report

### 7.2 Permission violation

If `PermissionDenied` is raised for a legitimate operation:

1. Check the agent's `ARQUX_AGENT_ROLE` env var
2. Verify the handler is not in `MUTATING_HANDLERS` for auditor role
3. If the handler should be allowed, file a bug — do NOT disable strict mode
4. **Never** set `ARQUX_STRICT_ROLES=0` in production to work around a permission issue

### 7.3 sync_brain errors

If `sync_brain` ERROR appears in logs:

1. Check that `meta-brain.cortex` contains `$2/DOM:arqux` entry
2. If missing, the workspace was initialized with a buggy version — re-init
3. Verify `arqux cortex-verify .arqux/meta-brain.cortex` passes
4. If issue persists, file a bug with full log output

---

## 8. Contact

- **Maintainer**: Fidel Lozada — https://github.com/FidelErnesto03
- **Security**: security@arqux.dev
- **Issues**: https://github.com/FidelErnesto03/arqux/issues

---

**Document version:** 1.0 (2026-07-12)
**ArqUX version:** 0.4.3+
