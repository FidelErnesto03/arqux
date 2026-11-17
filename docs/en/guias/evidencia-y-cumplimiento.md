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

# Evidence and compliance — CISO guide

*English translation — canonical source: `docs/es/guias/evidencia-y-cumplimiento.md`*

Operational guide for a compliance officer or external auditor. Walks the full signed-evidence cycle: generate a bundle without leaking private material, sign it with Ed25519, and verify it on your own ground without access to the workspace or the repository. Every claim ends in an executable command — if it cannot be executed, it is not claimed.

## Who this is for

For the evaluator who must decide whether the evidence ArqUX produces is admissible under their control framework. No trust in the vendor required: verification runs on the auditor's ground, with minimal material (the bundle + a public key).

## The evidence contract

**What leaves the workspace** (`arqux evidence export`):

| Content | Origin | Form |
|---|---|---|
| Session spans | `.arqux/timelog/SES*.cortex` | `SPN:` — session, agent identity, open/close, SHA-256 of the source timelog |
| Governance events | section `$5` of each timelog, sigils `AUD`/`DEC`/`ERR`/`LOOP` | verbatim lines |

**What never leaves**: chat transcripts, prompts, project source code, and every entry marked `visibility:"private"` — unless an explicit human decision (`--allow-raw`). The gate is *fail-closed*: given private material and no flag, export blocks.

## Procedure 1 — Keys and signing

```bash
# Generate Ed25519 pair (private seed + public, 0600 file)
arqux policy keygen .arqux/keys/emisor.key
# → key_id:8f3a…  created .arqux/keys/emisor.key

# Sign a document — appends the SIG:signature line to the file itself
arqux policy sign bundle.cortex --key .arqux/keys/emisor.key
# → signed bundle.cortex key_id:8f3a… payload_sha256:818b…

# Verify
arqux policy verify bundle.cortex --key .arqux/keys/emisor.key
# → SIGNATURE_VALID key_id:8f3a…   (exit 0)
```

The signature covers the document's **canonical bytes** (everything except `SIG:` lines). Ed25519 is a built-in implementation (RFC 8032, `signing.py`) — no external crypto dependency.

## Procedure 2 — Export with the three modes

Demonstration timelog: one session with three events, one marked `visibility:"private"`.

```bash
# Default mode: fail-closed gate
arqux evidence export --out bundle.cortex
# → EXPORT_BLOCKED: 1 private-marked field(s) found — export blocked.
#   Pass --redact-private to strip them or --allow-raw to include.   (exit 1)

# Redaction mode: private material is excluded and the count is recorded
arqux evidence export --out bundle.cortex --redact-private
# → bundle bundle.cortex spans=1 events=2 redacted=1

# Audit mode: private material leaves verbatim — explicit human decision
arqux evidence export --out bundle-raw.cortex --allow-raw
# → bundle bundle-raw.cortex spans=1 events=3 redacted=0
```

The flags are mutually exclusive. The resulting bundle declares its own state in `EVD:bundle{… redacted:1, raw:false}` — the auditor knows which mode was used without asking.

## Procedure 3 — External verification, without the workspace

The emitter hands the auditor **two artifacts**: the signed bundle and a public-key file. The private key (`seed:`) never leaves.

```bash
# EMITTER side — publish only the keypair's public: line
grep '^public:' .arqux/keys/emisor.key > emisor.pub

# AUDITOR side — empty directory, no repo, no emitter .arqux
mkdir -p audit/.arqux/keys
cp bundle.cortex emisor.pub audit/ && mv audit/emisor.pub audit/.arqux/keys/
cd audit

pip install arqux
arqux policy verify bundle.cortex
# → SIGNATURE_VALID key_id:8f3a…   (exit 0)

# Forgery test: one appended byte invalidates
echo 'AUD:e_9999{agent:"mallory"}' >> bundle.cortex
arqux policy verify bundle.cortex
# → ERR_INVALID_SIGNATURE: signature does not match document payload  (exit 1)
```

Without `--key`, `verify` resolves the public key by scanning for `public:` lines in `.arqux/keys/` next to the document — the auditor needs neither the full keypair nor the repository.

## Mechanism → compliance control

Careful language: ArqUX **provides evidence for** these controls; it certifies compliance with no framework.

| Mechanism | What it evidences for | Verification |
|---|---|---|
| `EVD` bundle + `SPN` spans with source-timelog SHA-256 | Execution traceability — who, when, on which artifact (EU AI Act logging art.; ISO 27001 A.8.15 logging) | `arqux evidence export --out …` |
| Ed25519 `SIG:signature` | Integrity and non-repudiation of the exported artifact (evidence custody) | `arqux policy verify` exit 0 / `ERR_INVALID_SIGNATURE` exit 1 |
| `visibility:"private"` gate + `redacted:N` | Data minimization on export — private material does not leave by default (GDPR minimization principle) | `EXPORT_BLOCKED` exit 1 without flag |
| Local governed state (`.arqux/` on owned disk) | Data residency — agent state lives on own infrastructure | filesystem inspection |
| Journal `ERR_CONFLICT_VERSION` | Shared-policy integrity — divergence detected, not silenced | `arqux push-delta` with a stale base |

## Honest limits

What this evidence does **not** guarantee:

1. **Content truthfulness** — the signature proves integrity and key origin, not that the agent told the truth when recording. A signed false event is a valid false event.
2. **Total coverage** — the bundle includes only what timelogs recorded in `$5` with sigils `AUD`/`DEC`/`ERR`/`LOOP`. Action without event = action without evidence.
3. **Impossibility of `--allow-raw`** — the gate demands a human decision, it does not technically prevent it. An operator with access can export private material; the control is procedural and stays marked (`raw:true`).
4. **Standard format** — the bundle is CODEC-CORTEX, not JSON/XML/SAML. Verifying it requires `pip install arqux` (or a parser for the format).
5. **Key custody** — the private key is a 0600 file. HSM/KMS/institutional rotation are the operator's responsibility.

## Appendix — what the external auditor checks, step by step

1. Receive `bundle.cortex` + `public:` file — **without** `seed:`. If the seed arrives, the delivery channel is wrong and gets reported.
2. `EVD:bundle{…}` — read `spans`, `events`, `redacted`, `raw`. `raw:true` demands an explanation from the emitter.
3. `arqux policy verify bundle.cortex` with the public key in `.arqux/keys/` → `SIGNATURE_VALID`.
4. Negative test: alter one line → `ERR_INVALID_SIGNATURE`. Confirms verification is not ceremonial.
5. For each `SPN:` — the `sha256` links the span to its source timelog; if required, the emitter can rehash the original timelog to corroborate.
6. Discrepancies (`ERR_KEY_MISMATCH`, `ERR_NO_SIGNATURE`, `ERR_KEY_NOT_FOUND`) escalate to the emitter with the exact output.

## References

- `THREAT_MODEL.md` — threat model with mechanisms and verification
- `EVIDENCE.md` — evidence artifact catalog with real fields
- `docs/es/especificacion/formato.md` — CODEC-CORTEX format

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
