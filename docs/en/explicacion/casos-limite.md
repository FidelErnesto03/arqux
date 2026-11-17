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

# System edge cases

*English translation — canonical source: `docs/es/explicacion/casos-limite.md`*

Five scenarios where "correct" behavior is not obvious. Each case states the expected behavior, the implemented reality, and the test that pins it — the test is the promise, the doc is the explanation.

## 1. Concurrent access to the same `.cortex` file

**Scenario:** two processes write the same `.cortex` at once.

- **Expected:** locking prevents corruption; the second writer waits or fails cleanly; zero loss.
- **Actual:** `security.py` implements locking via `fcntl.flock()`; `secure_write_cortex()` acquires an exclusive lock before writing; without the lock the operation fails with a clear error.
- **Test:** `tests/test_security.py::test_secure_write_cortex`

## 2. Empty `brain.cortex`

**Scenario:** workspace initialized with a brain with no entries or no sections.

- **Expected:** `sync_brain()` creates the default entries (IDN, FCS, OBJ, WRK, DOM:arqux) without crashing; the brain stays usable.
- **Actual:** `_build_brain_doc()` generates the complete template with all required sections; `_sync_meta_brain()` populates the meta-brain with `DOM:arqux`; an existing-but-empty brain is overwritten with the template by sync.
- **Test:** `tests/test_sync_brain.py::test_sync_brain_updates_wrk`

## 3. Invalid `.cortex` syntax

**Scenario:** a file with malformed entries, missing sections, invalid sigils.

- **Expected:** `cortex.verify()` detects and reports; invalid entries are flagged without taking the parser down; valid parts stay readable.
- **Actual:** the CODEC-CORTEX parser validates syntax strictly and returns a structured error list with line numbers; `cortex.verify` returns the verification report.
- **Test:** `tests/test_security.py::test_verify_cortex_missing_header_strict`

## 4. Nonexistent handler

**Scenario:** the CLI tries to invoke a handler absent from the REGISTRY.

- **Expected:** "unknown handler" error + list of available ones; no crash.
- **Actual:** `cli.py` checks REGISTRY before dispatch; the error includes the name and available handlers; `cmd_call` prints the error and exits cleanly.
- **Test:** `tests/test_cli.py::test_call_unknown_handler`

## 5. Missing identity file

**Scenario:** a handler reads an identity file (`identities/<id>.cortex`) that does not exist.

- **Expected:** `OUT-ERROR code=NOT_FOUND` with a descriptive message; no unhandled exception; the system keeps operating.
- **Actual:** `cortex.entry.get()` returns NOT_FOUND; identity-dependent handlers propagate the NOT_FOUND; the error is logged without crashing the process.
- **Test:** `tests/test_learn_trigger.py::test_learn_auto_trigger_on_record`

> The five cases converge on one principle: **the system reports, it does not crash** — every boundary (disk, format, registry, identity) has a point where failure becomes diagnosis instead of exception.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
