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

# TEST-SUITE-FRAMEWORK — Evidence-derived test suite

*English translation — canonical source: `docs/es/explicacion/test-suite-framework.md`*

**Document:** `TEST-SUITE-001`
**Version:** `0.1`
**Date:** `2026-11-13`
**Author:** Alfred — Architect's mandate
**Principle:** no test is invented. Every test derives from a **surfaced friction**, a
**recorded lesson** or a **closed issue** — and carries its provenance in its name or docstring.

---

## 0. Doctrine

1. **Mandatory regression:** every defect found produces a test that fails without the fix.
2. **The suite pays its cost:** tests discover real defects, not just freeze them.
3. **Gaps declared, not silenced:** an absent capability is an `xfail` with a reason; when
   implemented, the test XPASSes and forces it into a hard requirement.
4. **The artifact is verified, never the `ok`:** every assertion looks at the written file/state.
5. **Determinism:** no network, no dependent clocks, no inherited state (`tmp_path` fixtures).

---

## 1. Source → test map

### 1.1 · Ergonomics review 2026-11 (`CODEC-CORTEX/docs/CORTEX-DB-ERGONOMICS-REVIEW-2026-11.md`)

| # | Friction | Test | File | Status |
|---|---|---|---|---|
| 2.1 | Write ramp with tacit rules | `test_unbraced_attrs_value_is_accepted`, `test_name_collision_is_reported_never_silent` | `tests/e2e/test_ergonomics_contract.py` | ✅ |
| 2.2 | Dry-run lies; asymmetric metrics | `test_patch_dry_run_fails_where_apply_fails`, `test_entry_add/update_file_bytes_describe_the_real_file` | `tests/e2e/test_ergonomics_contract.py` | ✅ (real defect fixed) |
| 2.3 | Silent successes (empty checkpoint) | `test_empty_checkpoint_is_rejected_and_preserves_state` | `tests/e2e/test_ergonomics_contract.py` | ✅ |
| 2.5 | Session/identity walls | `test_switch_works_from_workspace_root`, `test_second_session_error_presents_alternatives`, `test_claim_without_bound_session_is_guided` | `tests/e2e/test_identity_session.py` | ✅ (real defect fixed) |
| 2.6 | No cross-corpus query exists | `test_cross_corpus_query_exists` | `tests/e2e/test_ergonomics_gaps.py` | ⚠️ declared xfail |
| 2.8 | Divergent CLI contracts | `test_first_level_project_and_cycle_commands_exist`, `test_call_accepts_file_payload`, `test_call_quiet_failure_sets_nonzero_exit` | `tests/e2e/test_transport_cli.py` | ✅ |
| 2.9 | Brain-centered validator; migration does not repair | `test_migration_reports_content_repairs` | `tests/e2e/test_ergonomics_gaps.py` | ⚠️ declared xfail |
| 2.10 | Late gates | `test_ready_reports_all_pending_placeholders_at_once` | `tests/e2e/test_integrity_gates.py` | ✅ |
| 2.11 | Errors in codes, not humans | `test_cycle_synthesize_without_braces_explains_the_expected_form`, `test_patch_failure_reports_selector_and_reason`, `test_cycle_synthesize_reports_hint_for_unbraced_content` | `test_ergonomics_contract.py`, `test_transport_cli.py` | ✅ |
| 2.12 | Codec backlog (U4 emit, U7, U10) | `test_public_emit_helper_is_exported` | `tests/e2e/test_ergonomics_gaps.py` | ⚠️ declared xfail |
| 1.1 | Deterministic context restore | `test_switch_dry_run_is_read_only` + mirror in `test_signal_quality` | `test_identity_session.py` | ✅ |
| 1.5 | Role separation | `test_forbidden_role_cannot_execute` | `tests/e2e/test_security_controls.py` | ✅ |

### 1.2 · Recorded lessons

| Lesson | What it demands | Tests | Status |
|---|---|---|---|
| `verifier_signal_noise` | health = E==0; deduped W; no W001 per entry | `test_healthy_brain_has_no_w001_name_noise`, `test_real_corruption_is_flagged_not_buried` | ✅ |
| `silent_corruption` | no `ok` with a damaged artifact | `tests/test_cortex_write_transaction.py` (14 tests), `test_blueprint_update_rejects_structural_markers_in_content`, `test_cycle_synthesize_treats_backslashes_literally` | ✅ |
| `contextual_identity` | identity from session, not transport | `test_claim_records_active_session_identity` | ✅ |
| `dos_controles_de_seguridad_distintos` | allow-list and root confinement, both | `test_undeclared_action_is_denied`, `test_declared_action_outside_root_is_denied`, `test_declared_action_inside_root_succeeds` | ✅ |
| `verificar_comportamiento_no_registro` | "recorded" is not "running" | `test_declared_action_inside_root_succeeds` (verifies FS effect) | ✅ |
| `defecto_no_es_decision` | (behavioral — not directly automatable) | — | 📝 human review |
| `layers` | capability survives without ArqUX | covered by `test_security_controls` (framework-independent executor) | ✅ partial |

### 1.3 · Closed issues as regression

| Issue (origin) | Defect | Test |
|---|---|---|
| 2026-11-13 kernel | `entry_add` truncates bodies with `key: value` | `tests/test_cortex_write_transaction.py` (full suite) |
| Manhattan cycle D1 | `blueprint_update` duplicates/merges markers | `test_blueprint_update_rejects_structural_markers_in_content` |
| Manhattan cycle D2 | `cortex_entry_update` splits values on internal commas | covered by integrity suite (phantom attrs) |
| Prior cycle/BLP | lost concurrent writes (~55%) | `test_concurrent_adds_do_not_lose_writes` |
| 2026-10-01 | `cycle.synthesize` expands `re.sub` backrefs | `test_backslash_payload_survives_synthesis` |
| 2026-10-02 | `blueprint.claim` uses transport identity | `test_claim_records_active_session_identity` |
| 2026-10-11 dogfood | opaque error, no `@file`/stdin, no subcommands | `tests/e2e/test_transport_cli.py` (5 tests) |

---

## 2. Real defects discovered by this suite (and fixed)

| Defect | Friction | Fix |
|---|---|---|
| `cortex.patch` approved nonexistent selectors in dry-run | 2.2 | dry-run resolves each selector with `crud_read`; no matches → `failed` |
| `identity.switch` from workspace root resolved the identity but delivered the handoff to root → opaque `NOT_FOUND` | 2.5 / 2.11 | handoff uses the context pointer's `project_root`; error with explicit remediation |

### 2.1 · Heimdall audit findings (2026-11-13, read-only)

| ID | Finding | Severity | Verified fix |
|---|---|---|---|
| HD-01 | The guard masked collateral damage when the same `SIGIL:name` lived in two sections | HIGH | Allowed sections resolved **before** mutating (`crud_read` on the selector); never by name. Tests: `test_guard_detects_collateral_on_same_name_in_other_section`, `test_update_with_section_selector_does_not_authorise_other_section` |
| HD-02 | BLP figures outdated | MEDIUM | Figures measured at signing time (this document and BLP-024 §3/§12/§13) |
| HD-03 | `blueprint.synthesize`'s MCP schema discarded `content` and the implementation ignored it | MEDIUM | `content` exposed in `input_schema` and **applied** (marker-safe write, `sections_written`). Tests: `test_blueprint_synthesize_schema_exposes_content`, `test_synthesize_with_content_actually_writes_sections` |
| HD-04 | `blp_markers@` written as invalid YAML (embedded quotes) | LOW | CSV string in quotes (valid YAML). Test: `test_blueprint_frontmatter_is_valid_yaml` |
| HD-05 | Guard rollback not atomic | LOW | temp + `fsync` + `os.replace` |
| HD-06 | Attrs with colon values reclassified as body | LOW | Declared risk (R-01); requires regression on real corpus |

**Permanent regression of the kernel incident (T-1.2):** `test_kernel_incident_regression` and
`test_kernel_like_document_roundtrip_preserves_every_body` reproduce the `AGENTS.md`-type
document and verify that appending to the same section does not truncate the prose.

---

## 3. How to run it

```bash
# e2e suite (evidence-derived)
./.venv/bin/python -m pytest tests/e2e -q

# full framework suite
PATH="$PWD/.venv/bin:$PATH" ./.venv/bin/python -m pytest tests/ -q
```

**Current baseline (measured when preparing 0.9.0):** `2708 passed · 2 skipped · 3 xfailed · 0 real failures`.
The total varies with the local `.cortex` corpus: `tests/test_cortex_migration.py` parametrizes over each file in the governance tree.
Breakdown of the derived suite: `tests/e2e` 46 passed + 3 xfailed · `tests/test_cortex_write_transaction.py`
18 passed. The only failure observed without the venv on `PATH` is environmental (`test_packaging` invokes the CLI).

---

## 4. Declared gaps (xfail)

1. **2.6 · cross-corpus query:** no per-corpus query handler exists; selectors
   address a single file. The most important internal ergonomic unlock (Platform).
2. **2.12/U4 · ideatic emit helper:** no public `emit` API for writing escaped
   CORTEX; today it is discovered by reading the package.
3. **2.9 · repairing migration:** `migrate` rewrites format but does not plan
   content repair (E032 in 6/7 identities post-migration).

**Rule:** when a gap closes, the test XPASSes and **must** become a hard requirement
in the same change.

---

### 1.4 · Documentation surfaces (2026-11-13 audit)

| Surface | Verification | File |
|---|---|---|
| Version | pyproject = runtime = README badge; fallback reads pyproject instead of a historical constant | `tests/e2e/test_docs_consistency.py` |
| Counts | README and HANDLERS.md agree with `handler_count()` | idem |
| Paths | `AGENTS.md` at root (not `.arqux/AGENTS.md`); PULSE inside `brain.cortex` (not `pulse.jsonl`) | idem |
| Installation | `pip install --pre arqux` while pre-release | idem |
| Changes | `CHANGELOG.md` with `[Unreleased]` section | idem |

## 5. Next blocks (not yet covered)

- **Property-based** (hypothesis): parse→write→parse roundtrip over generated corpus; fuzz
  attrs/bodies with quotes, braces and newlines.
- **Cross-runtime conformance** (Node/Bash/Go): the single CLI contract (2.8) is only
  tested in Python today.
- **Real migration** end to end with a legacy project.
- **Kernel budget:** ≤2,000-token limit and ≤40 per AXM line (test-verifiable).

---

*Every test cites its source. If a source has no test, it is a declared gap — never an oversight.*

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
