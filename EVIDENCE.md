# Evidence Model

> **Document version:** 1.0 (2026-07-12)
> **ArqUX version:** 0.4.3+

This document describes the evidence model in ArqUX: what evidence is, how it is recorded, how it is verified, and its limitations.

---

## 1. Overview

Evidence in ArqUX is the **append-only, tamper-evident** record of agent actions. Every state-mutating handler invocation generates an evidence entry that records who did what, when, and to what artifact.

Evidence serves three purposes:
1. **Auditability** — any stakeholder can review what happened and why
2. **Non-repudiation** — agents cannot deny having performed an action (HMAC-signed)
3. **Learning** — the learning engine mines evidence for patterns to elevate into lessons

---

## 2. Evidence Lifecycle

```
Agent invokes handler
  │
  ▼
Handler enforces permissions (ctx.check)
  │
  ▼
Handler executes mutation (e.g. blueprint.approve)
  │
  ▼
Handler calls evidence.record (or sync_brain does it implicitly)
  │
  ▼
evidence.record writes PULSE entry to brain.cortex
  │ - event_id: E-NNNN (sequential)
  │ - agent: ctx.agent_id
  │ - handler: e.g. "blueprint.approve"
  │ - task_id, cycle, blueprint (if applicable)
  │ - payload: string representation of inputs
  ▼
Auto-signing (P1-P): NOT applied on write — integrity verified on demand via `arqux cortex-verify` (BLP-014 reconciliation)
  │
  ▼
sync_brain updates meta-brain.cortex $2/DOM:arqux metrics
  │
  ▼
evidence.list / evidence.read for retrieval
```

---

## 3. Evidence Handlers

### 3.1 `evidence.record`

Records a new evidence entry in the brain's PULSE section.

**Input schema:**
```json
{
  "agent_id": "string (default: from ctx)",
  "handler": "string (canonical name)",
  "task_id": "string (optional)",
  "cycle": "string (optional)",
  "blueprint": "string (optional)",
  "payload": "string (inputs/outputs summary)"
}
```

**Output:** `OUT-WORK evidence.record ok event_id=E-NNNN`

**Permissions:** HMAC_REQUIRED — agent must be verified (in strict mode)

### 3.2 `evidence.list`

Lists evidence entries from the brain's PULSE section.

**Filters:** `agent`, `handler`, `cycle`, `task_id`, `since` (timestamp)

**Output:** `OUT-WORK events=N` with list of matching entries

**Permissions:** Read-only — allowed for all roles

### 3.3 `evidence.read`

Reads a single evidence entry by `event_id`.

**Input:** `event_id` (e.g. `E-0001`)

**Output:** Full entry detail

**Permissions:** Read-only — allowed for all roles

---

## 4. PULSE Entry Format

Each evidence entry is stored as a `SES` (session) sigil in the brain's `$8` PULSE section:

```
$8: PULSE

SES:E-0001{agent:"alfred", handler:"blueprint.approve", cycle:"CYCLE-01", blueprint:"BLP-005", payload:"approved after AC verification", ts:"2026-07-12T10:30:00Z"}
SES:E-0002{agent:"jarvis", handler:"task.complete", cycle:"CYCLE-01", task_id:"T-003", payload:"all tests pass", ts:"2026-07-12T10:35:00Z"}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent` | string | yes | Agent ID (from `ctx.agent_id`) |
| `handler` | string | yes | Canonical handler name |
| `task_id` | string | no | Task ID if handler operates on a task |
| `cycle` | string | no | Cycle ID if applicable |
| `blueprint` | string | no | Blueprint ID if applicable |
| `payload` | string | yes | Inputs/outputs summary (NOT the full payload) |
| `ts` | ISO 8601 | yes | Timestamp (UTC) |

### Limitations (current version)

- **`role` NOT recorded** — the agent's role is not persisted in the entry (planned for v0.5.0)
- **`ts` is implicit** — the event_id `E-NNNN` is sequential, not temporal; the `ts` field is planned for v0.5.0
- **No payload hash** — the `payload` field is a string summary, not a SHA-256 hash of the actual payload (planned for v0.5.0)

---

## 5. Integrity Verification

### 5.1 File-level integrity (current)

Every `.cortex` file (including `brain.cortex` with its PULSE section) is signed with a `$INTEGRITY` header:

```
# $INTEGRITY: sha256:abc123...
$0
# glossary...
$8: PULSE
SES:E-0001{...}
```

`arqux cortex-verify <path>` recomputes the SHA-256 of the content (excluding the header) and compares. Mismatch → `TamperError`.

### 5.2 Entry-level integrity (planned for v0.5.0)

Each PULSE entry will include a per-entry hash:

```
SES:E-0001{agent:"alfred", handler:"blueprint.approve", ..., hash:"sha256:..."}
```

The hash covers all other fields in the entry. This prevents an attacker from modifying a single entry without detection (current file-level hash detects any modification, but cannot pinpoint which entry was altered).

### 5.3 Non-repudiation (Ed25519, optional)

For high-assurance scenarios, `.cortex` files can be Ed25519-signed:

```
# $INTEGRITY: sha256:abc123...
# $SIGNATURE: ed25519:def456...
# $SIGNER: alfred
$0
...
```

`sign_cortex()` requires a private key (`private_key_pem` arg) and a signer name. `verify_cortex_signature()` requires the corresponding public key.

---

## 6. Audit Workflow

### 6.1 Daily audit

```bash
# List all evidence entries from today
arqux call evidence.list since=2026-07-12

# Verify brain integrity
arqux cortex-verify .arqux/brain.cortex
arqux cortex-verify .arqux/meta-brain.cortex

# Check for unexpected agents
arqux call evidence.list | grep -v "agent=alfred\|agent=jarvis\|agent=heimdall"
```

### 6.2 Weekly audit

```bash
# List all evidence from the past week
for day in Mon Tue Wed Thu Fri Sat Sun; do
  arqux call evidence.list since=2026-07-0$((RANDOM%9+1))
done

# Verify all .cortex files
find .arqux -name "*.cortex" -exec arqux cortex-verify {} \;
```

### 6.3 Incident investigation

If an incident is suspected:

1. **Freeze state** — stop all agents, do NOT modify `.arqux/`
2. **Verify integrity** — `find .arqux -name "*.cortex" -exec arqux cortex-verify {} \;`
3. **Export evidence** — `arqux call evidence.list > evidence-export.json`
4. **Identify timeline** — sort evidence by `ts` (or `event_id` order)
5. **Identify actor** — group by `agent`
6. **Cross-reference** — match evidence entries with handler outputs
7. **Restore** — `arqux restore <backup-before-incident>`

---

## 7. Limitations (current version)

| Limitation | Impact | Mitigation | Planned Fix |
|------------|--------|------------|-------------|
| `role` not recorded | Cannot audit which role an agent acted as | Cross-reference with `agents.cortex` | v0.5.0 |
| `ts` not explicitly recorded | Cannot sort chronologically (only by event_id) | Use event_id order (sequential) | v0.5.0 |
| No payload hash | Cannot verify payload integrity after the fact | Trust file-level hash | v0.5.0 |
| No entry-level hash | Cannot pinpoint which entry was tampered | File-level hash detects any change | v0.5.0 |
| Sequential event_id | Not globally unique across workspaces | Workspace-scoped is sufficient for pilot | v0.6.0 (UUID option) |
| No evidence export CLI | Must use `evidence.list` and pipe | Use `arqux call evidence.list > export.json` | v0.5.0 |

---

## 8. References

- [SECURITY.md](SECURITY.md) — security policy
- [THREAT_MODEL.md](THREAT_MODEL.md) — threat model
- [architecture/diagrams/learning-pipeline.puml](docs/architecture/diagrams/learning-pipeline.puml) — learning pipeline
- [PILOT_MODE.md](PILOT_MODE.md) — pilot deployment guide
