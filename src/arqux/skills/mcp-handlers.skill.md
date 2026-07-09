$0

# -- $0: MCP-HANDLERS SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Actor / workspace identity
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable principle
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler definition
# STP   | step       | attrs      | M | Working        | Configuration step / procedure
# LIM   | limit      | attrs      | M | Prefrontal     | Hard limit
# WRK   | work       | attrs      | B | Working        | Discovery / execution result


$1: ARCHITECTURE

IDN:mcp_handlers{ purpose:"Unified skill: MCP transport (how to connect) + handlers interface (what to do once connected). Serves agents on ANY platform (OpenCode, Claude, Cursor, Hermes, Codex). Platform-agnostic." }

AXM:handler_contract{ Every handler is a function registered in `arqux.handlers.REGISTRY` as a `HandlerSpec(name, fn, description, input_schema)`. The registry is the single source of truth — no parallel list is maintained. }

AXM:module_convention{ Handlers are grouped by module using dot notation: `<module>.<action>`. Valid modules: workspace, project, cycle, task, evidence, protocol, session, cortex, identity, blueprint, skill, setup. }

AXM:fixed_budget{ The handler surface has a fixed budget: adding a new handler requires removing one. This prevents scope creep and keeps the MCP surface lean. The budget is enforced by test_registry.py. }

AXM:governance_vs_utility{ Handlers fall into two categories: (1) governance handlers that mutate state (workspace, project, cycle, task, evidence, protocol, session, blueprint, skill, identity) and (2) utility handlers that read/inspect/render without side effects (cortex.*, setup.*). Governance handlers are the governed interface to Arqux state. }

AXM:no_auth_on_stdio{ For stdio transport, credentials come EXCLUSIVELY from environment variables (ARQUX_AGENT_ID, ARQUX_AGENT_ROLE). Do NOT advertise OAuth, bearer tokens, or custom auth capabilities in the MCP initialize response. This violates the MCP 2025-06-18 spec §Authorization and breaks clients (e.g. Codex) that attempt to negotiate unsupported auth. Transport rule: stdio → env vars, HTTP → OAuth 2.1. }


$2: MCP CONFIG UNIVERSAL

IDN:mcp_config{ purpose:"Configure the MCP server for any platform. MANDATORY on first session. Agents MUST load and execute before any governance operation." }

AXM:setup_required{ The agent MUST configure MCP before operating. Without MCP or CLI fallback, Arqux governance is unreachable. }

STP:env_config{
  ARQUX_AGENT_ID:"alfred (steward), jarvis (executor), heimdall (auditor), seshat (scribe). Default: anonymous.",
  ARQUX_AGENT_ROLE:"governor | executor | auditor. Default: governor (full access).",
}

AXM:config_first{ The agent MUST create the MCP config file if it does not exist. The config file location depends on the platform. Without it, the client will not detect the MCP server. }

STP:config_locations{
  opencode:"Workspace root: <workspace>/opencode.json (priority). Also: ~/.config/opencode/opencode.jsonc (fallback).",
  claude:"~/.config/claude/claude_desktop_config.json (mcpServers key).",
  cursor:"~/.cursor/mcp.json (mcpServers key).",
  generic:"Platform-specific. Key and fields depend on platform.",
}

STP:mcp_json{
  standard:"Key: mcpServers. Fields: command (string), args (array), env. (Claude, Continue, Cursor)",
  opencode:"Key: mcp. Fields: type:local, command (array), enabled:true, environment. (OpenCode CLI)",
  example_standard:{
    mcpServers:{
      arqux:{
        command:"arqux",
        args:["serve"],
        env:{
          ARQUX_AGENT_ID:"alfred",
          ARQUX_AGENT_ROLE:"governor"
        }
      }
    }
  },
  example_opencode:{
    mcp:{
      arqux:{
        type:"local",
        command:["arqux", "serve"],
        enabled:true,
        environment:{
          ARQUX_AGENT_ID:"alfred",
          ARQUX_AGENT_ROLE:"governor"
        }
      }
    }
  },
  note:"OpenCode: command is array [cmd, args...]. Standard (Claude/Cursor): command is string + args array + env (not environment).",
}

STP:verify{
  1:"Restart MCP client after config.",
  2:"Test: workspace.status or blueprint.list — should return data.",
  3:"Test: identity.record lesson=test kind=process — should return OK.",
  4:"If PERMISSION_DENIED: check env vars. Restart server and client.",
}


$3: CLI FALLBACK

IDN:cli_fallback{ purpose:"Agents without MCP (terminal-only, Codex) use CLI.", setup:"export ARQUX_AGENT_ID=alfred ARQUX_AGENT_ROLE=governor", usage:"arqux call <handler> <key=value...>" }

AXM:no_mcp_no_write{ If neither MCP nor CLI work, HALT. Report to Architect. Do NOT bypass with direct file edits. }


$4: ROLE MODEL

AXM:roles_not_enforced{ Arqux permission system trusts agents. Roles (governor, executor, auditor) guide intent but are NOT enforced at the handler level — `PermissionContext.check()` always passes. The behavioral contract in the agent's identity file is the real enforcement. }

STP:governor{ role:"governor", scope:"Creates structures (workspace, project, cycle, task, protocol). Assigns blueprints. Owns bootstrap. The default role when no ARQUX_AGENT_ROLE is set." }
STP:executor{ role:"executor", scope:"Claims and executes tasks. Updates progress, completes, fails. Claims blueprints and reports completion. Cannot create cycles or tasks." }
STP:auditor{ role:"auditor", scope:"Read-only. Can read any state (cortex.read, project.status, etc.) and record lessons. Cannot mutate governance state." }


$5: MCP WIRE PROTOCOL

AXM:dot_to_underscore{ The MCP protocol requires tool names matching `^[a-zA-Z0-9_-]+$`. Dots (.) in handler names are converted to underscores (_) on the wire. Example: `blueprint.create` → tool name `blueprint_create`. The internal registry preserves dotted names. Both names resolve at runtime. }


$6: QUICK REFERENCE — 72 HANDLERS

HDL:blueprint.ac{ signature:"ac(bp_id, ac_id, status, evidence?, reason?, path?)", purpose:"Verify one AC in §12. Fail triggers auto re-delegate (max 3)." }
HDL:blueprint.approve{ signature:"approve(bp_id, path?)", purpose:"Auditor approves after cross-verification. State → done." }
HDL:blueprint.assign{ signature:"assign(bp_id, executor, path?)", purpose:"Governor assigns an executor to the Blueprint." }
HDL:blueprint.block_for_architect{ signature:"block_for_architect(bp_id, path?)", purpose:"Block for Architect manual review after 3rd verification fail." }
HDL:blueprint.cancel{ signature:"cancel(bp_id, reason, path?)", purpose:"Cancel a Blueprint. Governor-only. State → cancelled." }
HDL:blueprint.claim{ signature:"claim(bp_id, path?)", purpose:"Executor claims the Blueprint. State → in_progress." }
HDL:blueprint.complete{ signature:"complete(bp_id, evidence, path?)", purpose:"Declare execution complete. State → review." }
HDL:blueprint.create{ signature:"create(obj, cycle?, path?)", purpose:"Create a new Blueprint from BLP_TEMPLATE.md in draft state." }
HDL:blueprint.define{ signature:"define(bp_id, pre?, scope?, exclusions?, acceptance_criteria?, procedure?, validations?, technical_design?, operational_design?, risks?, blocking_rule?, path?)", purpose:"Fill the Blueprint's definition sections. State → defined." }
HDL:blueprint.fail{ signature:"fail(bp_id, reason, path?)", purpose:"Blueprint hit an obstacle. State → blocked." }
HDL:blueprint.gate{ signature:"gate(bp_id, gate?, path?)", purpose:"Approve one or all Blueprint quality gates after Architect maturation." }
HDL:blueprint.list{ signature:"list(cycle?, status?, path?)", purpose:"List Blueprints with optional filters." }
HDL:blueprint.mature{ signature:"mature(bp_id, mode?, path?)", purpose:"Enter maturation phase. Mode 'live' (sync co-design) or 'async' (default, cyclic)." }
HDL:blueprint.re_delegate{ signature:"re_delegate(bp_id, path?)", purpose:"Re-delegate after verification fail (max 3 loops)." }
HDL:blueprint.read{ signature:"read(bp_id, format?, path?)", purpose:"Read a full Blueprint (HCORTEX or CORTEX format)." }
HDL:blueprint.ready{ signature:"ready(bp_id, path?)", purpose:"Architect declares Blueprint ready for execution." }
HDL:blueprint.task{ signature:"task(bp_id, task_id, status, evidence?, path?)", purpose:"Update one task's checkbox in §14." }
HDL:blueprint.update{ signature:"update(bp_id, note?, section?, content?, puml?, path?)", purpose:"Update Blueprint progress with a note or refine a section." }
HDL:cortex.entry.add{ signature:"entry.add(path, section, sigil, name, value, create_section?, force?)", purpose:"Add a new entry to a .cortex file." }
HDL:cortex.entry.delete{ signature:"entry.delete(path, selector, force?)", purpose:"Delete an entry matching a CORTEX selector." }
HDL:cortex.entry.get{ signature:"entry.get(path, selector)", purpose:"Read entries matching a CORTEX selector." }
HDL:cortex.entry.list{ signature:"entry.list(path, section?, sigil?)", purpose:"List entries in a .cortex file, optionally filtered." }
HDL:cortex.entry.move{ signature:"entry.move(path, selector, to_section)", purpose:"Move an entry between sections." }
HDL:cortex.entry.update{ signature:"entry.update(path, selector, set_?, replace_body?, append?, force?)", purpose:"Update an entry selected by a CORTEX selector." }
HDL:cortex.learn{ signature:"learn(scope?, path?)", purpose:"Scan a project brain through the Learning Engine. Returns scored entries." }
HDL:cortex.learn.elevate{ signature:"learn.elevate(candidate_id, apply?, confirm_hash?, path?)", purpose:"Elevate a learning candidate (SES→LNG or LNG→KNW)." }
HDL:cortex.read{ signature:"read(path)", purpose:"Read and parse a .cortex file using CODEC-CORTEX." }
HDL:cortex.render{ signature:"render(path)", purpose:"Render a .cortex file to HCORTEX READ markdown." }
HDL:cortex.render.diagram{ signature:"render.diagram(source, format?, path?)", purpose:"Render a PlantUML diagram to SVG/PNG." }
HDL:cortex.render.validate_file{ signature:"render.validate_file(path)", purpose:"Validate all PUML blocks in a file (D1-D5 checklist)." }
HDL:cortex.verify{ signature:"verify(path)", purpose:"Verify a .cortex file's structure using CODEC-CORTEX." }
HDL:cortex.write{ signature:"write(path, content, force?)", purpose:"Write (atomically) a .cortex file from CORTEX source text." }
HDL:cycle.close{ signature:"close(cycle_id, summary, path?)", purpose:"Close a cycle (no new tasks can be added)." }
HDL:cycle.create{ signature:"create(name, description, path?)", purpose:"Open a new cycle in the active project." }
HDL:cycle.current{ signature:"current(path?)", purpose:"Get the currently active cycle." }
HDL:cycle.list{ signature:"list(status?, path?)", purpose:"List cycles in the active project." }
HDL:evidence.list{ signature:"list(task_id?, cycle?, since?, limit?, path?)", purpose:"Query the evidence trail." }
HDL:evidence.read{ signature:"read(event_id, path?)", purpose:"Read a single evidence event by ID." }
HDL:evidence.record{ signature:"record(task_id, kind, payload, path?)", purpose:"Append an evidence entry to pulse.jsonl." }
HDL:identity.record{ signature:"record(lesson, kind?, cause?, agent_id?, path?)", purpose:"Record a behavioral lesson into the agent's identity file." }
HDL:project.bind{ signature:"bind(agent_id, role, path?)", purpose:"Bind an agent identity to the current project with a role." }
HDL:project.init{ signature:"init(name, path?, seed?)", purpose:"Initialize .arqux/ in a project directory and register it in the workspace." }
HDL:project.lessons{ signature:"lessons(path?)", purpose:"List lessons local to the current project." }
HDL:project.status{ signature:"status(path?)", purpose:"Active project status (cycles, tasks, agents)." }
HDL:project.unbind{ signature:"unbind(agent_id, path?)", purpose:"Release an agent binding from the current project." }
HDL:protocol.adopt{ signature:"adopt(agent_id, role, path?)", purpose:"Onboard an agent with a role." }
HDL:protocol.pause{ signature:"pause()", purpose:"Suspend governance for the current session without losing state." }
HDL:protocol.release{ signature:"release(agent_id, path?)", purpose:"Fully detach an agent (clean exit, no orphans)." }
HDL:protocol.resume{ signature:"resume()", purpose:"Resume governance after a pause." }
HDL:session.close{ signature:"close(summary, blps?, tasks?, decisions?, gaps?, path?)", purpose:"Close session and write portable SES entry to brain PULSE." }
HDL:session.context.get{ signature:"context.get(path?)", purpose:"Read the current context pointer and return formatted header." }
HDL:session.context.set{ signature:"context.set(project, scope, blp?, path?)", purpose:"Set the current session context pointer. Validates project exists." }
HDL:session.resume{ signature:"resume(path?)", purpose:"Read last SES entry from brain PULSE and restore the context." }
HDL:session.status{ signature:"status(path?)", purpose:"Read SES metadata without restoring full context." }
HDL:setup.plantuml{ signature:"plantuml(force?, path?)", purpose:"Download and install plantuml.jar to ~/.arqux/bin/." }
HDL:skill.convert{ signature:"convert(name, path?)", purpose:"Convert a skill from original format to CORTEX ultra-dense." }
HDL:skill.edit{ signature:"edit(name, content?, section?, path?)", purpose:"Edit (read/write/section-edit) a skill file in .arqux/skills/." }
HDL:skill.evolve{ signature:"evolve(name, adaptation_id, apply?, path?)", purpose:"Apply an approved adaptation to a skill. Default is dry-run." }
HDL:skill.import{ signature:"import(source, name, content?, path?)", purpose:"Acquire a skill from external source, store original in originals/." }
HDL:skill.list{ signature:"list(path?)", purpose:"List all available skills in .arqux/skills/." }
HDL:skill.record{ signature:"record(name, expected, actual, reason, path?)", purpose:"Record a deviation (ADA) when a skill does not match the real context." }
HDL:task.claim{ signature:"claim(task_id, path?)", purpose:"An executor claims a task → status: in_progress." }
HDL:task.complete{ signature:"complete(task_id, evidence, path?)", purpose:"Mark a task done and record evidence." }
HDL:task.create{ signature:"create(obj, pre?, proc?, ac?, blk?, assignee?, complexity?, priority?, path?)", purpose:"Create a governed task in the current cycle." }
HDL:task.fail{ signature:"fail(task_id, reason, path?)", purpose:"Mark a task blocked and record the cause." }
HDL:task.list{ signature:"list(status?, assignee?, cycle?, path?)", purpose:"List tasks with filters." }
HDL:task.read{ signature:"read(task_id, format?, path?)", purpose:"Read a task (CORTEX or HCORTEX format)." }
HDL:task.update{ signature:"update(task_id, note, status?, path?)", purpose:"Update task progress, optionally change status." }
HDL:workspace.init{ signature:"init(path?)", purpose:"Initialize .arqux/ at the workspace root." }
HDL:workspace.lessons{ signature:"lessons(project?, path?)", purpose:"List lessons elevated to the meta-brain." }
HDL:workspace.status{ signature:"status(verbose?, path?)", purpose:"Workspace status (OUT-MIN by default)." }


$7: HOW TO EXTEND

WRK:add_handler{
  1:"Define your handler function in the appropriate module under `src/arqux/handlers/<module>.py`.",
  2:"Register it in `src/arqux/handlers/__init__.py` using the _register(_spec(...)) pattern.",
  3:"Add the handler name to the module count dict in `test_registry.py::test_module_handler_counts`.",
  4:"Add permission entries in `permissions.py` (GOVERNOR_ONLY, EXECUTOR_ALLOWED, or READ_ONLY_PREFIXES).",
  5:"Run `python -m pytest tests/test_registry.py -v` to verify.",
}

LIM:no_duplicate_registration{ severity:"blocking", limit:"Never register a handler with the same name twice. __init__.py raises RuntimeError('duplicate handler') on collision." }
