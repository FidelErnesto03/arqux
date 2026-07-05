# CYCLE-00: Initial Skeleton

Bootstrap the framework structure with placeholder name support and the
brain-as-shared-mind architecture (handoffs and pulse live INSIDE the
brain, not in separate files).

## Scope
- Create directory layout per the brief's §6 Fase 0
- Implement all handlers as MCP-callable functions
- Add the placeholder rename script (scripts/rename-product.py)
- Wire the dogfooding directory (.arqux/) with manifest + meta-brain + projects
- Add the test suite covering happy paths
- Integrate handoffs and pulse into the brain's # HANDOFFS and # PULSE sections
- Define HCORTEX as a markdown writing discipline (not a separate format)
- Document learning layers: behavioral (identity) vs. contextual (project) vs. global (workspace)

## Exit Criteria
- `python scripts/rename-product.py <name> --dry-run` produces a valid diff
- `pytest` passes for all handler modules
- `pip install -e .` succeeds (after rename)
- `arqux --version` prints the version
- No `pulse.jsonl` file is created by any handler — pulse lives in brain
- No `bindings.cortex` file is created — sessions live in brain

## Metadata
- **status:** open
- **created:** 2026-07-04
