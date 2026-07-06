# Changelog

All notable changes to Arqux are documented here.

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
