# Changelog

All notable changes to Arqux are documented here.

## [0.4.0] — 2026-07-08

### Added
- **security.py**: HMAC-SHA256 identity verification for MCP handlers
- **security.py**: SHA-256 integrity hashes for .cortex files (tamper detection)
- **security.py**: Ed25519 optional signing for non-repudiation
- **concurrency.py**: File locking and placeholder-based ID generation
- **cycle.mature handler**: Transition draft → ready (closes ALTO-1)
- **enum Role**: GOVERNOR, EXECUTOR, AUDITOR with enforcement (closes MEDIO-3)
- Backward-compat mode via ARQUX_STRICT_SECURITY and ARQUX_STRICT_ROLES env vars

### Changed
- **permissions.py**: Role enforcement with HMAC verification
- **sync.py**: Fixed GAP-001 sync_brain path double-bug
- **handlers/cycle.py**: create_cycle now writes draft status explicitly
- **handlers/cortex.py**: HMAC verification on record_lesson_handler
- **handlers/blueprint.py**: Uses concurrency.next_blueprint_id_safe
- Handler count: 71 → 72 (cycle.mature added)

### Fixed
- CRÍTICO-1: Identity bypass (HMAC-SHA256)
- CRÍTICO-2: Evidence tampering (SHA-256 + Ed25519)
- ALTO-1: Workflow incomplete (cycle.mature)
- ALTO-2: ID non-determinism (concurrency file locking)
- MEDIO-1: sync_brain double path (GAP-001)
- MEDIO-2: Version inconsistency (1.0.0 → 0.4.0)
- MEDIO-3: Permission API incomplete (enum Role + enforcement)

## [0.3.5] — 2026-07-08

### Changed
- README rebranded to Architectural User Experience with Hexagon Contract
- License aligned to Apache-2.0 across all surfaces

## [1.0.0] — 2026-07-06

### Added
- 54 MCP handlers across 11 modules (workspace, project, cycle, task, evidence, protocol, cortex, identity, skill, blueprint, setup)
- Blueprint lifecycle: 14 handlers (create, define, mature, ready, assign, claim, update, complete, fail, cancel, approve, re_delegate, block_for_architect, read, list)
- 3-phase conversational adoption protocol (DISCOVER → ADOPT → GOVERN)
- HCORTEX output format: vertical layout, tables, lists, diagrams
- CLI universal fallback: `arqux call <handler>` works without MCP
- 3-layer learning engine: behavioral (identity.record), contextual (cortex.learn), procedural (skill lifecycle)
- 7 skills in CORTEX format (adoption, handlers, identities, cortex, mcp, learning, workflows)
- 10 templates including BLP_TEMPLATE.md (18 sections) and CYCLE_MANIFEST_TEMPLATE.md (9 sections)
- PlantUML integration: local render server + cortex.render.diagram handler
- Quality contract (6 gates) for Blueprints and Cycles
- Cross-verification with auto-re-delegation (max 3 loops)
- Default governor role — no env var configuration needed

### Changed
- AGENTS.md simplified to 67-line entry point with skill references
- MCP tool names: dots → underscores (protocol compliant)
- CortexOUT serialization: always returns plain string
- All Hermes-specific references removed — platform agnostic

### Fixed
- blueprint.define body population (was writing template placeholders)
- blueprint.ready quality gates verification (was allowing skip)
- Permissions: identity.record allowed for all roles
- MCP default role changed from auditor to governor
