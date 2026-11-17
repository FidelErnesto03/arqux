---
doc_type: explanation
status: informative
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
<p align="center"><sub>Explanation · Informative · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Codec boundary — codec-cortex 1.0.x

*English translation — canonical source: `docs/es/explicacion/frontera-codec.md`*

The codec is a **format convention**, not the owner of governance semantics.

## What ArqUX consumes from `codec-cortex>=1.0,<1.1`

| Capability | Codec surface | ArqUX adapter |
|---|---|---|
| Strict 1.0 parse | `codec_cortex.dispatcher.parse_cortex` | `model.from_codec_v1` → `arqux.cortex.model` |
| Canonicalization / hashing | `canonicalize` (via `_bind_v1_api`, no live consumer yet), `hash_cortex` | v1 binding in `core/state`; `hash_cortex` is native `arqux.security` |
| HCORTEX compilation (write side) | `compile_hcortex` | render boundary in `core/state` |

## What ArqUX does NOT consume (native, own)

| Capability | Owner | Notes |
|---|---|---|
| Learning engine | `core/learning/` | the codec removed `learning` in 1.0 — fully native since the learning rework; `grep -rInE "cortex\.learning\|codec_cortex\.learning" src/arqux/` must stay empty |
| Governance validation (E0xx) | `cortex/level_policy.py` | policy ported onto the native model; equivalence vs legacy verified on the fixture corpus |
| `$N/SIGIL:name` selectors | `cortex/selectors.py` | consumed by the CRUD layer |
| HCORTEX reading | `cortex/read_renderer.py` | renderer ported onto the native model |
| Writer | `cortex/writer.py` | unconditionally emits the 1.0 dialect: `$0:format{cortex:1.0, encoding:UTF-8}` + executable declarations (I001/G010/G022/G025), `open:true` contracts |
| Brain mutation | `core/state/_crud.py` | read → mutate → re-serialize → **strict re-parse** → validate → atomic write; a serialization that fails re-parse aborts (silent_corruption axiom) |

## Explicitly out of scope

- `slots`, `migrate`, codec harness modules — unused in ArqUX.
- Legacy sigil `GSIG:` — promoted to executable declarations on write; never emitted.
- Legacy pseudo-section `$0.1` — normalized to `$19` on write.

## Sync policy (when CODEC-CORTEX evolves)

1. The pin is `>=1.0,<1.1`: minor bumps are adopted on release; major lines require a new Blueprint.
2. On a codec upgrade: run `test_cortex_v1_conformance.py` in a clean venv — re-verifies parse/validate/render equivalence against the legacy baseline.
3. If the codec adds a capability ArqUX already owns (validate, selectors, render-read), ArqUX keeps its implementation — governance semantics are not outsourced.
4. A codec regression that breaks `can_parse` is surfaced by `codec_cortex_diagnostics()` — never silently degraded.

## Environment model

| Environment | Binding | Role |
|---|---|---|
| `codec-cortex 1.0.x` installed | `api='v1'` | **Canonical** — the pin; the suite must hold delta 0 |
| Only legacy `cortex` 0.6.x | `api='legacy'` | Degraded but functional (tolerant parser) |
| No codec | `available=False` | ArqUX's native reader/writer keeps operating; codec-dependent paths report, they do not crash |

**Why the boundary exists:** the `.cortex` format belongs to the codec; the *governance* (which sections, which sigils, which invariants) belongs to ArqUX. The fail-closed boundary guarantees a write never passes unvalidated — and that ArqUX can operate degraded if the codec is absent.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
