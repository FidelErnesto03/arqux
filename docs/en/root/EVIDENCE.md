---
doc_type: report
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
<p align="center"><sub>Report · Normative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# ArqUX evidence model

English twin of the canonical [`EVIDENCE.md`](../../../EVIDENCE.md).

What constitutes evidence in ArqUX 1.0.0, with which real fields, who writes it, who verifies it and what is explicitly out. Written for the auditor: every claim is verifiable against the code or a generatable artifact.

## What evidence is in ArqUX

Evidence is the **append-only, tamper-evident** record of agent actions. Every state-mutating handler invocation produces an entry: who did what, when and on which artifact. It serves three purposes:

1. **Auditability** — any party can review what happened and why.
2. **Verifiable integrity** — per-`.cortex`-file SHA-256 seal; altering one byte breaks verification.
3. **Learning** — the learning engine mines evidence to elevate patterns into lessons.

## Evidence artifact catalog

### 1. Timelog — `.arqux/timelog/SES<NNN>_<timestamp>.cortex`

Native per-session work record. Real sections:

| Section | Sigil | Real fields |
|---|---|---|
| `$1 IDENTITY` | `TLG:identity` | `project`, `ses`, `opened` (ISO-8601 UTC), `version`, `revision` |
| `$2 ACTIVITIES` | `ACT:<name>` | `start`, `end`, `state` (open/closed), `last_activity`, `revision` |
| `$3 RECEIPTS` | `RCV:<name>` | External projection receipt |
| `$4 PROJECTIONS` | `PRJ:<name>` | Per-provider projection mark |

Every interval carries ISO-8601 UTC timestamps and a `revision` counter incremented on each write.

### 2. Cycle seal — `seal.cortex`

`seal_sha256:"<hex>"` — SHA-256 hash of the artifact. **Verification**: `arqux cortex-verify <file>` recomputes every declared hash and fails on any divergence.

### 3. Evidence bundle — `arqux evidence export`

Generates a consolidated `.cortex` with root sigil `EVD` and per-type events:

| Sigil | Content |
|---|---|
| `ARQX` | Artifact metadata |
| `SPN` | Execution span (session interval) |
| `AUD` | Audit event |
| `DEC` | Decision event |
| `ERR` | Error event |
| `LOOP` | Loop event |

**Mandatory privacy**: export scans timelogs for `private`-marked fields. If it finds any, it **blocks** with `PermissionError` unless `--redact-private` (strips them from the bundle) or `--allow-raw` (includes them, explicit decision) is passed. There is no silent mode.

### 4. Ed25519 signatures — REQ-12

Real (not optional) signature: `arqux policy sign <doc> <key>` appends a `SIG:signature` entry to the `.cortex` document; `arqux policy verify <doc>` validates it. The signature covers the document's canonical bytes **excluding** its own `SIG:` lines — altering any other attribute produces `ERR_INVALID_SIGNATURE`. `generate_keypair` produces the key pair.

### 5. Journal — `journal.cortex` (REQ-13)

Authoritative multi-workspace sync record: `JRN:journal{version, deltas, rules, updated}`. **Optimistic locking**: a push declares its `base_version`; if it does not equal the journal's current version, the push is rejected — divergence stays visible, never silently overwritten. `$3 POLICY` publishes the authoritative rules (`pull_policy`).

## Chain of custody

| Artifact | Written by | Verified by |
|---|---|---|
| Timelog | Per-session lifecycle handlers | `arqux cortex-verify` + section reads |
| Seal | Handler at cycle seal | `arqux cortex-verify` (recomputes SHA-256) |
| Bundle | `arqux evidence export` | Field↔timelog diff + privacy gate |
| Signature | `arqux policy sign` (Ed25519) | `arqux policy verify` |
| Journal | `push_delta` with `base_version` | Stale-base rejection + `journal_version` |

## What is NOT evidence in ArqUX

Declared explicitly so the auditor does not over-infer:

- **The brain is not evidence**: `brain.cortex` is mutable working state (focus, lessons, sessions). Evidence lives in timelogs and the append-only PULSE.
- **BLPs are not evidence**: they are plans. Evidence of their execution lives in PULSE and artifacts.
- **Screenshots and terminal logs are not evidence**: the `AUD`/`DEC`/`ERR` event persisted in `.cortex` is.
- **A bundle without seal or signature is an export, not proof**: it gains probative value when verified against timelogs and the seal.
- **`private` marks do not leave in the bundle by default**: exportable evidence is, by design, a subset of internal evidence.

## Declared maturity

| Piece | 1.0.0 status |
|---|---|
| Timelog with timestamps and revisions | Implemented |
| Verifiable SHA-256 seal | Implemented |
| Bundle export with privacy gate | Implemented (REQ-11) |
| Ed25519 sign/verify signature | Implemented (REQ-12) |
| Journal with optimistic locking | Implemented (REQ-13) |
| HMAC-SHA256 in agent-identity authentication | Implemented (`security.py` — agent↔workspace message signing) |

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
