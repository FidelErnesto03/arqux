# ADR 0001 — Titularidad y licencia del motor de aprendizaje

**Status:** Accepted — 2026-11-14 (Arquitecto)
**Decider:** Arquitecto, 2026-11-14
**Scope:** `src/arqux/core/learning/**`, `tests/test_learning_*.py`, `tests/fixtures/learning/**`

## Context

`codec-cortex 1.0.0` removed the `cortex.learning` module by constitutional
mandate (Article III: a kernel package shall not import or depend on a
learning engine; §21 lists learning as a forbidden capability, see
`governance/DEPENDENCY_POLICY.md` in CODEC-CORTEX). Any release that
follows the certificate — `arqux[codec]` installing codec ≥1.0 — ships an
`arqux` whose `cortex.learn` is **silently degraded** (`ENGINE_UNAVAILABLE`,
empty candidates).

The Arquitecto has ruled that the learning engine is part of ArqUX, not of
CODEC-CORTEX. CODEC-CORTEX is a format convention. This ADR records how
the source is taken over and under which license.

## Decision

**Via A — Apache-clean, no code lineage from the codec.**

Actions:

1. Rewrite the learning algorithms from the *documented semantics* of the
   CLE in codec 0.6.2 (public behaviour, determinism, edge cases).
2. Do **not** copy source code from `cortex/learning/*.py` — not even
   re-indented or renamed. The codec is MPL-2.0 (weak copyleft on the
   covered components); copying would taint the Apache tree.
3. Do **not** absorb `workspace.py` (ArqUX has no `.cortex/` workspace
   layer), `apply_patch` / `verify_post_apply` (dead imports — writes go
   through `arqux.state.crud_add`), or `explain_candidate` (unused).
4. `src/arqux/` remains **Apache-2.0**. No ADR supersedes this — any
   future change is a new ADR.

## Absorbed symbols (native re-implementation)

| Origin (codec 0.6.2) | Native replacement | Notes |
|---|---|---|
| `cortex.learning.candidates.detect_candidates` | `arqux.core.learning.algorithms.candidates.detect_candidates` | Same shape: list[Candidate] |
| `cortex.learning.index.rebuild_index` | `arqux.core.learning.algorithms.index.rebuild_index` | In-memory; no workspace |
| `cortex.learning.policy.parse_policy_document` | `arqux.core.learning.algorithms.policy.parse_policy_document` | Native `POL:` parse; raises on invalid input |
| `cortex.learning.elevation.plan_patch` / `render_diff` | `arqux.core.learning.algorithms.elevation.plan_patch` / `render_diff` | Critical-sigil protection preserved |
| `cortex.learning.scoring.score_candidate` | `arqux.core.learning.algorithms.scoring.score_candidate` | Same weights, documented |
| `write_cortex = None` hack | **Removed** — `arqux.cortex.writer` remains the only write path | |

## Excluded symbols

| Symbol | Reason |
|---|---|
| `workspace.py` | No `.cortex/` workspace in ArqUX; the engine operates on project brains only |
| `apply_patch` | Dead import; writes go through `arqux.state.crud_add` |
| `verify_post_apply` | Depends on `apply_patch`/`rebuild_for_workspace`; not needed in the native path |
| `explain_candidate` | Not used by any ArqUX handler |
| `learning_flow` | Unused by ArqUX; out of scope |

## Consequences

- `pip install arqux` **without** the `codec` extra ships a fully functional
  learning engine. The `codec` extra remains only to drive `cortex.verify`
  and `cortex.read/write` on raw `.cortex` files.
- `arqux --version` may report a learning backend named
  `native` (this ADR) — it is not a version of `codec-cortex`.
- The former silent-degradation path (`_HAS_CLE=False` + `[]`) is removed.
  Callers must surface `learning_engine_available() -> (bool, cause)`.
- Tests: `tests/test_learning_golden.py` asserts behaviour against fixtures
  authored in ArqUX (see T-2.2); `tests/test_learning_document_adapter.py`
  asserts the CORTEX-dict → learning-document adapter.

## Evidence

- `src/arqux/core/learning/protocol.py` — protocol (no codec imports)
- `src/arqux/core/learning/document.py` — adapter (no codec imports)
- `src/arqux/core/learning/errors.py` — native taxonomy
- `src/arqux/core/learning/algorithms/` — native algorithm package
- `grep -rnE "^(from|import) (cortex|codec_cortex)" src/arqux/core/learning/` → **empty**
