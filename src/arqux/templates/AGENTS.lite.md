$0

# -- $0: SIGIL GLOSSARY --
# Sigil | Name    | Type   | Risk | Layer      | Description
# AXM   | axiom   | cuerpo | H    | Prefrontal | Non-negotiable principle
# LIM   | limit   | attrs  | M    | Prefrontal | Hard limit or restriction
# WK    | workflow| cuerpo | B    | Working    | Execution procedure
# REG   | handler | attrs  | B    | Semantic   | MCP handler registration


$1: LITE DELTA — GOVERNANCE BASICS

AXM:delta_lite{This file is a DELTA over AGENTS.md (NANO). Load AGENTS.md first. Adds 20 governance-basics handlers. Does NOT repeat NANO content}
AXM:skill_resolution{Skills live in workspace .arqux/skills/. Walk UP from cwd→find .arqux/→read .arqux/skills/<skill>.md}
WK:skill_protocol{protocol.skill.md:Session start, interaction protocol, HCORTEX discipline, decision frameworks, blockers}
AXM:governance_basics{LITE tier enables Blueprint lifecycle, task management, evidence recording. Mutations via MCP handlers}
AXM:checkpoint_rule{Checkpoint via blueprint.task()+evidence.record() after each task. NEVER batch checkpoints}
LIM:no_full_arsenal{severity:info, scope:tier, status:current, limit:"FULL handlers unavailable in LITE. Load AGENTS.full.md for complete arsenal"}
WK:lite_boot{procedure:(a)Load AGENTS.md (b)Detect tier (c)If LITE or FULL:load this file (d)Call handler.list(tier=LITE) to discover handlers (e)Resolve skills (f)Operate}


$2: LITE HANDLER DISCOVERY

REG:handlers_lite{tier:LITE, discover:"handler.list", adds_to:NANO}
AXM:lite_discovery{Call handler.list(tier=LITE) to discover available handlers. The LITE tier adds governance basics (blueprint lifecycle, task management, evidence) to the NANO kernel. No hardcoded handler table.}

# LITE END — Load AGENTS.full.md for full arsenal (>250K window).
