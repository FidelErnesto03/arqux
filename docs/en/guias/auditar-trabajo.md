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

# Auditing an agent's work

*English translation — canonical source: `docs/es/guias/auditar-trabajo.md`*

Review ritual for whoever signs off on someone else's work: **review → integrity → actors → decision**. ~10 minutes the first time; ~2 minutes as routine.

```text
1. arqux review --cycle CYCLE-NN    → what was done, with metrics
2. arqux cortex-verify <file>       → integrity was not altered
3. arqux call evidence.list         → who did what, when
4. You decide: approve or escalate  → with data, not faith
```

## Step 1 — Read the cycle review

```bash
$ arqux review --cycle CYCLE-16
# Cycle Review — CYCLE-16

| Field | Value |
|---|---|
| Status | active |
| Seal | `none` |
| Entries | 2 |
| Tasks | 0 |

## Evidence (HCORTEX — round-trippable)
## §19: ARQUX METADATA
## §1: CYCLE
...
```

What to look at in the output:

| Field | Where | Suspicious if |
|---|---|---|
| `Status` | header | `closed` with no seal, or a "finished" cycle still `active` |
| `Seal` | header | `none` on a cycle that should be closed and sealed |
| `Entries`/`Tasks` | header | 0 entries on a cycle reporting completed work |
| `§` sections | HCORTEX body | empty or missing evidence sections |

The HCORTEX body is round-trippable: it is the cycle state compiled to readable format — `loss_count == 0` means nothing was lost on recompilation (REQ-09).

## Step 2 — Verify integrity

```bash
$ arqux cortex-verify .arqux/brain.cortex
OK: .arqux/brain.cortex integrity verified
```

- Exit `0` = integrity verified; exit `1` = tampering or missing header.
- `.cortex` files written with the integrity chain carry `# $INTEGRITY: sha256:<hash>` on their first line — verify rehashes the content and compares.

**Real protection demo** (a `$INTEGRITY` file, one byte altered):

```bash
$ arqux cortex-verify /tmp/integrity-tampered.cortex
FAIL: integrity violation in /tmp/integrity-tampered.cortex:
expected=496280aa97…, actual=2a90e64f6a…
# exit code 1
```

> **Honest detail:** `verify` checks the `$INTEGRITY` header when present — a file without it passes without comparison. A cycle's strong layer is its **seal**.

### The cycle seal (strong layer)

When a cycle closes (`cycle.close`), ArqUX writes `seal.cortex`: one SHA-256 per `.cortex` artifact in the cycle plus a root hash over the set, anchored in the MANIFEST (`seal_sha256`). Running `cortex-verify` on `seal.cortex` **recomputes every hash** and reports `ERR_HASH_MISMATCH` on any drift (REQ-03).

> seal = **integrity** ("the content did not change"), Ed25519 signature = **non-repudiation** ("who produced it"). For bundle signature verification: [evidence & compliance guide](evidencia-y-cumplimiento.md).

## Step 3 — Trace actors

```bash
$ arqux call evidence.list cycle=CYCLE-16
OUT-WORK events=SES021-E0001,SES022-E0001,...,SES022-E0099
total=105 returned=100 offset=0 next_offset=100 storage=brain.pulse
```

- `evidence.list` filters by `task_id`, `cycle`, `since` (paginated `limit`/`offset`).
- Each event carries its session in the ID (`SES022-E0093` → session 22, event 93): **who and when** without digging through logs.
- `evidence.read event_id=SES022-E0093` gives the event detail.
- Audit events sign as `OUT-AUDIT` — if the executor reports "verified" but the evidence carries no independent audit, it was not audited.

## Approval checklist

- [ ] `review` shows the cycle/BLP ACs marked and evidence linked
- [ ] `Seal` present if the cycle is closed (or you understand why `none`)
- [ ] `cortex-verify` OK on key artifacts; seal OK if present
- [ ] `evidence.list` shows events consistent with what was reported (same tasks, expected actors)
- [ ] No pending `drift` (`arqux drift-check` if you use projections)

## Signals that demand escalation

- `Seal` missing on a closed cycle, or MANIFEST `seal_sha256` mismatch
- `ERR_HASH_MISMATCH` / `integrity violation` on any artifact — **approve nothing**
- Evidence events that do not match claimed tasks
- "Verified" ACs with no associated `OUT-AUDIT`
- Cycle `Status` inconsistent with the executor's verbal report

Escalating = opening an issue + asking the governor for a formal `OUT-AUDIT` verification. Signed evidence exists precisely so this conversation stays short.

## The ritual, timed (real example)

| Minute | Action |
|---|---|
| 0–2 | `review --cycle` — overview and evidence sections |
| 2–4 | `cortex-verify` on key artifacts / seal |
| 4–7 | `evidence.list` — actors and event chain |
| 7–10 | checklist + decision |

As routine (~2 min): the three commands plus a glance at the checklist. The first time costs more because you are calibrating what normal looks like — time well spent.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
