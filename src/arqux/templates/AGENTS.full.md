$0

# -- $0: SIGIL GLOSSARY --
# Sigil | Name    | Type   | Risk | Layer      | Description
# AXM   | axiom   | cuerpo | H    | Prefrontal | Non-negotiable principle
# LIM   | limit   | attrs  | M    | Prefrontal | Hard limit or restriction
# WK    | workflow| cuerpo | B    | Working    | Execution procedure
# REG   | handler | attrs  | B    | Semantic   | MCP handler registration


$1: FULL DELTA — COMPLETE ARSENAL

AXM:delta_full{This file is a DELTA over AGENTS.lite.md. Load AGENTS.md+AGENTS.lite.md first. Adds ~63 handlers. Does NOT repeat NANO or LITE content. Only load if context window >250K}
AXM:skill_resolution{Skills live in workspace .arqux/skills/. Walk UP from cwd→find .arqux/→read}
WK:skill_protocol{protocol.skill.md:Session start, interaction protocol, HCORTEX discipline}
WK:handler_discovery{handler.list(tier):Dynamic handler discovery from MCP registry. Replaces static documentation.}
WK:skill_cortex{cortex.skill.md:CORTEX format, HCORTEX output, native memory, PUML diagrams}
WK:skill_diagram{diagram.skill.md:PUML diagram creation, validation, publishing}
WK:skill_learning{learning.skill.md:3 levels—conductual, contextual, procedimental}
WK:skill_workflows{workflows.skill.md:10 canonical workflows with PlantUML diagrams}
AXM:dogfood{Framework governs its own development. Every feature→governed task. Bug→handler missing. Iterate}
WK:full_boot{procedure:(a)Load AGENTS.md (b)Load AGENTS.lite.md (c)Detect tier (d)If FULL:load this file (e)Call handler.list(tier=FULL) to discover handlers (f)Resolve ALL skills (g)Operate full arsenal}

AXM:full_arsenal{FULL tier enables ALL handlers. handler.list(tier=FULL) returns the complete registry.}
$2: FULL HANDLER DISCOVERY

REG:handlers_full{tier:FULL, discover:"handler.list", adds_to:LITE}
AXM:full_discovery{Call handler.list(tier=FULL) to discover all available handlers. The FULL tier adds the complete arsenal: learning engine, skill management, infrastructure. No hardcoded handler table.}
# FULL END — All handlers available.
