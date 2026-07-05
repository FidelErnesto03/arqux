# Changelog

All notable changes to Arqux are documented here.
Per the dogfooding rule (§8 of the brief), this file should be generated
from `evidence.list` rather than written by hand. During initial development
it is maintained manually; once CYCLE-99 (release v1.0) is governed by the
framework itself, it will be regenerated from evidence.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial package skeleton with placeholder product name.
- Six handler modules: `workspace`, `project`, `cycle`, `task`, `evidence`, `protocol`.
- 24 MCP handlers covering the full governance surface.
- Three identity roles: `governor`, `executor`, `auditor` with permission middleware.
- CORTEX-OUT output profiles: `OUT-MIN`, `OUT-WORK`, `OUT-AUDIT`, `OUT-FULL`, `OUT-ERROR`.
- CLI commands: `arqux serve`, `arqux init`, `arqux status`.
- CODEC-CORTEX integration via `pyproject.toml` dependency.
- Rename script `scripts/rename-product.py` for placeholder → real name swap.
- Dogfooding directory `.arqux/` with `CYCLE-00` initialized.
- Test suite covering happy paths for every handler module.

### Notes
- Product name is shipped as the `arqux` placeholder token.
- Run `python scripts/rename-product.py <name>` before `pip install -e .`.

## [1.0.0] — TBD

Will be tagged when CYCLE-99 (release cycle) is governed end-to-end by the framework itself.
