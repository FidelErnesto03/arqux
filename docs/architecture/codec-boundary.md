# Codec Boundary — codec-cortex 1.0.x

BLP-005 / CYCLE-16. The codec is a **format convention**, not the owner of
governance semantics (§4 of BLP-005; Art. III §21 of the standard).

## What ArqUX consumes from `codec-cortex>=1.0,<1.1`

| Capability | Codec surface | ArqUX adapter |
|---|---|---|
| Strict 1.0 parse | `codec_cortex.dispatcher.parse_cortex` | `model.from_codec_v1` → `arqux.cortex.model` |
| Canonicalization / hashing | `canonicalize` (bound via `_bind_v1_api`, no live consumer yet), `hash_cortex` | `core.state` v1 binding; `hash_cortex` is native `arqux.security` |
| HCORTEX compile (write-side) | `compile_hcortex` | renderer boundary in `core/state` |

## What ArqUX does NOT consume (native, owned)

| Capability | Owner | Notes |
|---|---|---|
| Learning engine | `core/learning/` | codec removed `learning` in 1.0 — fully native since BLP-002/003/004; `grep -rInE "cortex\.learning\|codec_cortex\.learning" src/arqux/` must stay empty |
| Governance validation (E0xx) | `cortex/level_policy.py` | ported policy over the native model; equivalence vs legacy verified on the fixture corpus |
| Selectors `$N/SIGIL:name` | `cortex/selectors.py` | consumed by the CRUD layer |
| HCORTEX READ | `cortex/read_renderer.py` | ported renderer over the native model |
| Writer | `cortex/writer.py` | emits the 1.0 dialect unconditionally: `$0:format{cortex:1.0, encoding:UTF-8}` + executable declarations (I001/G010/G022/G025), `open:true` contracts |
| Brain mutation path | `core/state/_crud.py` | read → mutate → re-serialize → **strict re-parse** → validate → atomic write; a serialization that does not re-parse aborts (silent_corruption) |

## Explicitly out of scope

- Codec `slots`, `migrate`, harness modules — unused by ArqUX.
- `GSIG:` legacy declaration sigil — upgraded to executable declarations on
  write; never emitted.
- `$0.1` legacy metadata pseudo-section — normalized to `$19` on write
  (BLP-041).

## Sync policy (when CODEC-CORTEX evolves)

1. Pin is `>=1.0,<1.1`: minor bumps adopt on release; major lines require a
   new blueprint.
2. On codec upgrade: run `test_cortex_v1_conformance.py` under a clean venv —
   it re-verifies parse/validate/render equivalence vs the legacy baseline.
3. If the codec adds a capability ArqUX already owns (validate, selectors,
   render-read), ArqUX keeps its implementation — governance semantics are
   not outsourced.
4. A codec regression that breaks `can_parse` is surfaced by
   `codec_cortex_diagnostics()` — never silently degraded.

## Environment model

| Environment | Binding | Role |
|---|---|---|
| `codec-cortex 1.0.x` installed | `api='v1'` | **Canonical** — the pin; suite must hold delta 0 |
| Legacy `cortex` 0.6.x only | `api='legacy'` | Degraded but functional (tolerant parser) |
| No codec | `available=False` | ArqUX native reader/writer still operate; codec-dependent paths report, not crash |
