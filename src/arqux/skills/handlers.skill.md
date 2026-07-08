$0

# -- $0: HANDLERS SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Actor / workspace identity
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler definition
# STP   | step       | attrs      | M | Working        | Procedure step
# LIM   | limit      | attrs      | M | Prefrontal     | Hard limit
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable principle


$1: ARCHITECTURE

AXM:handler_contract{ Every handler is a function registered in `arqux.handlers.REGISTRY` as a `HandlerSpec(name, fn, description, input_schema)`. The registry is the single source of truth — no parallel list is maintained. }

AXM:module_convention{ Handlers are grouped by module using dot notation: `<module>.<action>`. Examples: `workspace.init`, `blueprint.create`, `cortex.read`. Valid modules: workspace, project, cycle, task, evidence, protocol, session, cortex, identity, blueprint, skill, setup. }

AXM:fixed_budget{ The handler surface has a fixed budget: adding a new handler requires removing one. This prevents scope creep and keeps the MCP surface lean. The budget is enforced by test_registry.py. }

AXM:governance_vs_utility{ Handlers fall into two categories: (1) governance handlers that mutate state (workspace, project, cycle, task, evidence, protocol, session, blueprint, skill, identity) and (2) utility handlers that read/inspect/render without side effects (cortex.*, setup.*). Governance handlers are the governed interface to Arqux state. }


$2: DISCOVERY

WRK:list_handlers{
  1:"Run `python -c 'from arqux.handlers import list_handlers, handler_count; print(f\"Total: {handler_count()}\"); print(*list_handlers(), sep=\"\\n\")'` from the ARQUX project root.",
  2:"Run `python -c 'from arqux.handlers import REGISTRY; print(*{n.split(\".\")[0] for n in REGISTRY}, sep=\"\n\")'` to list all modules.",
  3:"Or inspect the MCP tool list at runtime — the MCP server exposes every registered handler as a tool with its description and input schema.",
}

AXM:live_source{ The handler list is a live registry. Never hardcode handler counts or names in documentation — always derive from REGISTRY or MCP tool list. }


$3: ROLE MODEL

AXM:roles_not_enforced{ Arqux permission system trusts agents. Roles (governor, executor, auditor) guide intent but are NOT enforced at the handler level — `PermissionContext.check()` always passes. The behavioral contract in the agent's identity file (AXM:architect_first, LIM:no_auto_commit) is the real enforcement. }

STP:governor{ role:"governor", scope:"Creates structures (workspace, project, cycle, task, protocol). Assigns blueprints. Owns bootstrap. The default role when no ARQUX_AGENT_ROLE is set." }
STP:executor{ role:"executor", scope:"Claims and executes tasks. Updates progress, completes, fails. Claims blueprints and reports completion. Cannot create cycles or tasks." }
STP:auditor{ role:"auditor", scope:"Read-only. Can read any state (cortex.read, project.status, etc.) and record lessons. Cannot mutate governance state." }


$4: MCP WIRE PROTOCOL

AXM:dot_to_underscore{ The MCP protocol requires tool names matching `^[a-zA-Z0-9_-]+$`. Dots (.) in handler names are converted to underscores (_) on the wire. Example: `blueprint.create` → tool name `blueprint_create`. The internal registry preserves dotted names. Both names resolve at runtime. }


$5: WORKFLOW PATTERNS

HDL:workspace.init{ signature:"init(path?)", purpose:"Bootstrap. Creates .arqux/ + AGENTS.md + identities/ + skills/. Only needed once per machine." }
HDL:project.init{ signature:"init(name, path?, seed?)", purpose:"Initialize .arqux/ inside a project. seed= pre-populates brain.cortex. This is the entry point for project governance." }
HDL:blueprint.create{ signature:"create(obj, cycle?, path?)", purpose:"Create a BLP from template. State → draft." }
HDL:blueprint.define{ signature:"define(bp_id, scope, acceptance_criteria, procedure, ...)", purpose:"Fill definition sections. State → defined." }
HDL:blueprint.mature{ signature:"mature(bp_id, mode?)", purpose:"Enter maturation (async or live co-design). State → maturing." }
HDL:blueprint.approve{ signature:"approve(bp_id, path?)", purpose:"Auditor approves. State → done." }

AXM:blueprint_flow{ The canonical blueprint lifecycle: create → define → mature → ready → assign → claim → execute (task.*) → complete → approve. Each state transition is a handler call. See workflows.skill.md w01 for the full state machine diagram. }

AXM:session_persistence{ Session state is persisted via session.close (writes SES to brain PULSE) and restored via session.resume. Always close sessions before ending a work block. }


$6: HOW TO EXTEND

WRK:add_handler{
  1:"Define your handler function in the appropriate module under `src/arqux/handlers/<module>.py`.",
  2:"Register it in `src/arqux/handlers/__init__.py` using the _register(_spec(...)) pattern.",
  3:"Add the handler name to the module count dict in `test_registry.py::test_module_handler_counts`.",
  4:"Add permission entries in `permissions.py` (GOVERNOR_ONLY, EXECUTOR_ALLOWED, or READ_ONLY_PREFIXES).",
  5:"Run `python -m pytest tests/test_registry.py -v` to verify.",
}

LIM:no_duplicate_registration{ severity:"blocking", limit:"Never register a handler with the same name twice. __init__.py raises RuntimeError('duplicate handler') on collision." }
