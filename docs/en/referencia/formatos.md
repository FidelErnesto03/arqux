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

# Product artifact formats

*English translation — canonical source: `docs/es/referencia/formatos.md`*

Specification of the `.cortex` artifacts ArqUX 1.0.0 produces as output: cycle seal, evidence bundle, policy journal, signed document and HCORTEX report. Each format declares its producer, captured real structure, privacy policy and executable verification. The base CORTEX dialect (sigils, sections, types) belongs to `docs/en/especificacion/formato.md` — this document covers the concrete instances.

## Summary

| Artifact | Producer | Verifier |
|---|---|---|
| `seal.cortex` | `cycle.close` (REQ-03) | `arqux cortex-verify` → `ERR_HASH_MISMATCH` |
| `bundle.cortex` | `arqux evidence export` (REQ-11) | `arqux policy verify` after signing |
| `journal.cortex` | `arqux push-delta` (REQ-13) | `arqux pull-policy` + `ERR_CONFLICT_VERSION` |
| Signed document | `arqux policy sign` (REQ-12) | `arqux policy verify` → `SIGNATURE_VALID` |
| HCORTEX report | `arqux review --cycle` (REQ-09) | `arqux from-hcortex` (round-trip) |

## 1. `seal.cortex` — closed-cycle seal

When a cycle closes, every `.cortex` artifact in the cycle directory is hashed on disk; the root seal is the SHA-256 over the digests ordered by file.

```cortex
$0
$0:format{cortex:1.0, encoding:UTF-8}

# -- $0: GLOSSARY --
# SEL | seal   | attrs | H | Root seal of a closed cycle
# HSH | hash   | attrs | M | Per-artifact SHA-256 record
SEL:sel_contract{type:"attrs", weight:"H", focus:"seal_sha256", fields:"cycle:text|seal_sha256:text|artifacts:int", desc:"Cycle seal", open:true}
HSH:hsh_contract{type:"attrs", weight:"M", focus:"file", fields:"file:text|sha256:text", desc:"Artifact hash", open:true}

$1: SEAL
SEL:seal{cycle:"CYCLE-99", seal_sha256:"0b7b7e34…8103dba", artifacts:2}
HSH:cycle_cortex{file:"cycle.cortex", sha256:"148fcf40…1e3cb"}
HSH:tasks_t1_cortex{file:"tasks/t1.cortex", sha256:"37be4d77…eba35"}
```

| Field | Type | Meaning |
|---|---|---|
| `SEL:seal.cycle` | text | Name of the sealed cycle |
| `SEL:seal.seal_sha256` | hex 64 | SHA-256 over the concatenated ordered digests |
| `SEL:seal.artifacts` | integer | Artifacts covered |
| `HSH:*.file` | relative path | Artifact inside the cycle directory |
| `HSH:*.sha256` | hex 64 | Digest of the file on disk at close |

**Verification**: `arqux cortex-verify seal.cortex` recomputes each `HSH` against the file on disk. Drift → `FAIL: [ERR_HASH_MISMATCH] <file>: recorded=… actual=…` (exit 1). The root `seal_sha256` is also in the cycle `MANIFEST.md` front-matter.

**Privacy**: filenames and hashes only — no content.

## 2. `bundle.cortex` — evidence export

Produced by `arqux evidence export`. Packages session spans and governance events from the `SES*.cortex` timelogs.

```cortex
$0

$0:format{cortex:1.0, encoding:UTF-8}

ARQX:arqx_contract{…}   EVD:evd_contract{…}   SPN:spn_contract{…}
AUD:aud_contract{…}     DEC:dec_contract{…}   ERR:err_contract{…}
LOOP:loop_contract{…}

$19: ARQUX METADATA
ARQX:artifact{level:0, name:"evidence-2026-11-15T21:52:10Z", usage:"export", kind:"bundle"}

$1: EVIDENCE
EVD:bundle{generated:"2026-11-15T21:52:10Z", project:"ciso-sbx", spans:1, events:2, redacted:1, raw:false}

$2: SPANS
SPN:ses999{session:"SES999", identity:"alfred", opened:"2026-11-15T10:00:00Z", closed:"2026-11-15T11:00:00Z", sha256:"2a802e5f5def5127", source:"SES999_20261115_100000.cortex"}

$3: EVENTS
AUD:e_0001{ts:"2026-11-15T10:05:00Z", agent:"alfred", action:"blueprint.claim", target:"BLP-016"}
ERR:e_0003{ts:"2026-11-15T10:30:00Z", code:"ERR_DEMO", recovered:"true"}
```

| Field | Type | Privacy |
|---|---|---|
| `EVD:bundle.generated/project` | text | Public |
| `EVD:bundle.spans/events/redacted` | integer | Public — counters, not content |
| `EVD:bundle.raw` | bool | `true` = exported private verbatim (demands justification) |
| `SPN:*.sha256` | hex 16 | Source-timelog digest — links span↔origin |
| `$3` events | `AUD/DEC/ERR/LOOP` sigils | Timelog `$5` section only; `visibility:"private"` blocked or redacted |

**Privacy policy**: no flag → `EXPORT_BLOCKED` (exit 1) if any `visibility:"private"` line exists in the timelogs. `--redact-private` excludes those entries and records the count. `--allow-raw` includes them verbatim — audit use, stays marked `raw:true`.

**Verification**: after signing, `arqux policy verify bundle.cortex` → `SIGNATURE_VALID`. Structure parseable by any CODEC-CORTEX reader.

## 3. `journal.cortex` — authoritative policy journal

Produced by `arqux push-delta`. Location: the workspace's `.arqux/journal/journal.cortex`. Optimistic locking: a delta applies only if its `base_version` equals the current version.

```cortex
$1: JOURNAL
JRN:journal{version:1, deltas:1, rules:1, updated:"2026-11-15T21:54:30Z"}

$2: DELTAS
DLT:ws-demo_1{workspace:"ws-demo", base_version:0, new_version:1, rules:1, sha256:"ce3f6a48b374f3a8", applied:"2026-11-15T21:54:30Z"}

$3: POLICY
RUL:no_raw_private{check:"secret_pattern", action:"deny", when:"export", desc:"deny raw private fields"}
```

| Field | Type | Meaning |
|---|---|---|
| `JRN:journal.version` | integer | Current version — monotone counter of the optimistic lock |
| `JRN:journal.deltas/rules` | integer | Counters for sections `$2`/`$3` |
| `DLT:*.base_version/new_version` | integer | Version the emitter built the delta on |
| `DLT:*.sha256` | hex 16 | Applied delta digest — traceability |
| `RUL:*` | attrs | Current enforce rule (`check`, `action`, `when`) |

**Verification**: `arqux pull-policy` renders the current policy; `arqux push-delta --base <stale>` → `ERR_CONFLICT_VERSION: journal is at version 1, delta claims base 0 — human triage required` (exit 1). Divergence is detectable — never silently overwritten.

**Privacy**: policy rules only — carries no evidence or session data.

## 4. Signed document — `SIG:signature`

`arqux policy sign <doc> --key <keypair>` appends a `SIG:signature` entry to the end of the document and injects `SIG:sig_contract` into `$0` if missing (the signed document stays self-contained).

```cortex
SIG:signature{algo:"ed25519", key_id:"e417895894ab81f5", payload_sha256:"818b5eaff4c92643…", sig:"51649b615c50682ef1…"}
```

| Field | Type | Meaning |
|---|---|---|
| `algo` | text | Always `ed25519` (RFC 8032, own implementation) |
| `key_id` | hex 16 | First 16 chars of the public key |
| `payload_sha256` | hex 64 | Digest of the signed canonical bytes |
| `sig` | hex 128 | Ed25519 signature over the canonical text (full document minus `SIG:` lines) |

**Verification**: `arqux policy verify <doc>` → `SIGNATURE_VALID` (exit 0). Possible errors: `ERR_INVALID_SIGNATURE` (altered content), `ERR_NO_SIGNATURE` (no SIG entry), `ERR_KEY_MISMATCH` (signed by another key), `ERR_KEY_NOT_FOUND` (no resolvable public in `.arqux/keys/`).

**Privacy**: the signature proves integrity and origin — it does not hide content. External verification uses only the keypair's `public:` line; the `seed:` never leaves (see `docs/en/guias/evidencia-y-cumplimiento.md`).

## 5. HCORTEX report — `arqux review`

`arqux review --cycle <id>` renders the cycle to Markdown for human review. The `<!-- HCORTEX v=0.1 t=canonical -->` block embeds the CORTEX entries as comments — the report is **round-trippable**: `arqux from-hcortex report.md` recompiles the original `.cortex`.

```markdown
# Cycle Review — CYCLE-16

| Field | Value |
|---|---|
| Status | active |
| Entries | 2 |

## Evidence (HCORTEX — round-trippable)

<!-- HCORTEX v=0.1 t=canonical -->
<!-- glossary
$0
$0:format{cortex:1.0,encoding:UTF-8}
ARQX:arqx_contract{...}
-->
```

**Verification**: `arqux from-hcortex <report.md>` regenerates the artifact — the human form and the machine form do not diverge.

**Privacy**: mirrors the cycle's content — the project's same publication rules apply.

## What this specification does not cover

Internal governance formats (brain, timelogs, blueprints, handoffs) belong to the canon in `docs/en/especificacion/`. Versions: this specification describes ArqUX 1.0.0 — an artifact from a different version may vary; the `ARQX:artifact` and `EVD:bundle` fields declare their own context.

## References

- `docs/en/especificacion/formato.md` — base CORTEX dialect
- `docs/en/guias/evidencia-y-cumplimiento.md` — full CISO flow with these artifacts
- `THREAT_MODEL.md` — integrity mechanisms behind each format

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
