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

# Contributing to ArqUX

English twin of the canonical [`CONTRIBUTING.md`](../../../CONTRIBUTING.md).

Thanks for your interest. This guide takes you from `git clone` to a green PR: reproducible setup, tests, conventions and what to expect from review.

**Before you start:** for non-trivial changes, open an issue first — a large PR without prior discussion will likely be closed.

## Development setup

Requirements: Python 3.11+ and pip (or [uv](https://docs.astral.sh/uv/) — see below).

```bash
git clone https://github.com/FidelErnesto03/arqux.git
cd arqux
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

The `dev` extra installs: pytest, pytest-asyncio, pytest-cov, ruff, mypy and pre-commit.

**uv alternative:** `uv sync --group dev` uses the `dev` group from `[dependency-groups]` (newer versions, no mypy).

**Note:** the pre-commit hook invokes `uv run ruff` — if you do not have uv on PATH, install it (`pip install uv`) or run `ruff check --fix src/ tests/` manually before committing.

### Verification

```bash
pytest -q                    # full suite
pytest tests/e2e -q          # end-to-end only
ruff check src/ tests/       # linter (CI mirror)
mypy src/arqux/              # types (pip dev extra)
python scripts/check_surfaces.py  # homologation: 115 handlers, version
```

## Contribution flow

1. **Fork** + branch from `main`: `git checkout -b feat/my-change` (or `fix/`, `docs/`).
2. Small commits with clear messages in English — the repo uses conventional style (`feat:`, `fix:`, `docs:`).
3. `pytest -q`, `ruff check` and `check_surfaces` green locally before opening the PR.
4. Open the PR describing the **why** of the change and how it was verified.
5. CI runs pytest + ruff (`.github/workflows/ci.yml`).

## Conventions

- **Code:** English; `ruff` formats and lints (`ruff check --fix` is applied by the hook).
- **User documentation:** Spanish is canonical in `docs/es/`; English mirrors live in `docs/en/`. Technical identifiers and code are always in English.
- **Claims:** documentation is verified against the code — do not assert what you cannot run.
- **Internal process:** the core team works with governed cycles and Blueprints (`.arqux/`). As an external contributor you **do not need** that system: plain issues + PRs are enough.

## Tests

- Where they go: `tests/test_<feature>.py` for unit tests; `tests/e2e/` for full flows; `tests/fixtures/` for test data; `tests/benchmarks/` for performance.
- Registered markers (`--strict-markers`): `slow` and `integration`. Mark slow tests with `@pytest.mark.slow`.
- `asyncio_mode = "auto"`: async tests need no decorator.
- A new test must fail before the fix and pass after — that is the repo's doctrine.

## Contributing documentation

- Every doc carries YAML front-matter: `doc_type` (`tutorial|guide|reference|explanation|canon|report`), `status` (`normative|informative`), `version`, `verified` (date).
- `docs/es/` follows the taxonomy: `tutorial/`, `guias/` (guide), `referencia/` (reference), `explicacion/` (explanation), `especificacion/` (canon). `docs/en/` mirrors it 1:1 — same relative path and filename, English body.
- Register new docs in the corresponding index (`docs/es/README.md` / `docs/en/README.md`).
- Verify: `pytest tests/test_frontmatter_consistency.py tests/e2e/test_docs_consistency.py tests/e2e/test_docs_contract.py -q`.
- Registry-derived tables (like the one in `PERMISSIONS.md`) are **regenerated with their script**, never hand-edited.

## What we do not ask for

- Massive formatting/rename PRs without a prior issue
- New features without prior discussion
- Changes that loosen fail-closed checks to "make CI pass"
- Invented versions or counts in documentation

## Review

A maintainer reviews the PR; they may request changes or split the work. PRs merge with green CI. If there is no response in a reasonable time, a polite bump is fine.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verified 2026-11-15 · <a href="../../../docs/en/README.md">documentation index</a></sub></p>
<!-- /DOC-FOOT -->
