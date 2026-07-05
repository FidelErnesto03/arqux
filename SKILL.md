$0

# -- $0: ARQUX SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Skill identity
# FCS   | focus      | attrs      | H | Working        | Active focus
# OBJ   | objective  | attrs      | H | Working        | Active objective
# STP   | step       | attrs      | M | Working        | Procedure step
# KNW   | knowledge  | attrs      | B | Semantic       | Knowledge item
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson
# DEP   | depend     | attrs      | B | Semantic       | Dependency


$1: IDENTITY

IDN:arqux{name:"Arqux", type:"framework", version:"1.0.0", purpose:"Minimum-viable governance framework for AI agent teams", dependency:"codec-cortex>=0.4.0"}

FCS:current{what:"Govern ARQUX itself under its own protocol (dogfooding)", priority:"high", status:"current"}

OBJ:dogfood{goal:"Every feature is implemented as a governed task under ARQUX", status:"current", success:"All handlers proven via self-governance"}
OBJ:stable{goal:"57+ tests passing, canonical CORTEX output, zero regressions", status:"current", success:"Testsuite green"}


$2: DEPENDENCIES

DEP:codec{package:"codec-cortex", version:">=0.4.0", purpose:"CORTEX parser, writer, validator"}
DEP:python{version:">=3.11", purpose:"Runtime for CLI and MCP server"}
DEP:click{purpose:"CLI framework"}
DEP:mcp{purpose:"MCP protocol server"}


$3: ARCHITECTURE

KNW:modules{list:"cli, state, formats, server, permissions, cortex_out, handlers (7 files)", core:"state.py = persistence layer, formats.py = CORTEX conversion"}
KNW:handlers{total:30, governance:24, utility:4, protocol:2, surface:"workspace(3) project(5) cycle(4) task(7) evidence(3) protocol(4) cortex(4)"}
KNW:persistence{format:"CODEC-CORTEX sigil with $0 glossary", stems:"brain, manifest, meta-brain, projects, cycle, T-NNN"}


$4: OPERATION

STP:install{action:"pip install arqux", result:"CLI + MCP server available"}
STP:init{action:"arqux init", result:".arqux/ + AGENTS.md in cwd"}
STP:mcp{action:"hermes mcp add arqux --command arqux --args serve", env:["ARQUX_AGENT_ID=alfred", "ARQUX_AGENT_ROLE=governor"]}
STP:govern{action:"project.init(name=X, path=./X, seed=...)", note:"Unique entry point for project governance"}


$5: LESSONS

LNG:path_param{type:"process", lesson:"Siempre pasar path explícito a handlers de descubrimiento. El cwd del MCP no es confiable."}
LNG:format_canonical{type:"format", lesson:"Archivos .cortex con writer canónico de CODEC-CORTEX. Attrs en una línea, cuerpo multilínea."}
LNG:identities_scope{type:"rule", lesson:"Identidades solo a nivel workspace. Proyectos no tienen identities/ propio."}
LNG:startup_flow{type:"process", lesson:"project.init es el ÚNICO entry point para gobernar un proyecto. NO usar cortex.write para gobernanza."}
