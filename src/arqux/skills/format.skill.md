$0

# -- $0: FORMAT SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# AXM   | axiom      | cuerpo     | H | Prefrontal     | File convention
# LIM   | limit      | attrs      | M | Prefrontal     | Hard limit
# KNW   | knowledge  | attrs      | B | Semantic       | Format explanation


$1: EXTENSION RULES

AXM:extension_rule{ .cortex = state files (brain, manifest, tasks, cycles, identities). .md = agent bootstrapping files (AGENTS.md, SKILLs). Content defines format. cortex CLI parses CORTEX regardless of extension. }

AXM:no_auto_hcortex{ HCORTEX .md twins are NOT auto-generated. Request them on demand via cortex.render MCP handler when the Architect needs human review. }


$2: CANONICAL FORMAT

AXM:attrs_single_line{ Entradas attrs se escriben en UNA linea. LNG:name{type:"process", lesson:"texto"}. NO multilinea con indentacion. Esto maximiza densidad de informacion para el LLM y evita errores de formato. }

AXM:cuerpo_multiline{ Entradas cuerpo (AXM, DESC) se escriben en multilinea preservando el texto literal. El escritor canónico de CODEC-CORTEX normaliza attrs y preserva cuerpo. }

LIM:no_cortex_write_for_governance{ limit:"Do NOT use cortex.write for governance files. Use project.init(seed=) and governance handlers.", severity:"blocking" }


$3: WRITER

KNW:writer{ tool:"write_cortex() via formats.py", behavior:"Uses CODEC-CORTEX CortexDocument -> write_cortex() for canonical output. Falls back to string builders if unavailable.", stems:"brain, manifest, meta-brain, projects, cycle, T-NNN" }
