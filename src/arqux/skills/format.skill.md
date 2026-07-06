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

AXM:attrs_single_line{ Attrs entries are written in ONE line. LNG:name{type:"process", lesson:"text"}. NO multiline with indentation. This maximizes information density for the LLM and avoids formatting errors. }

AXM:cuerpo_multiline{ Body entries (AXM, DESC) are written in multiline preserving literal text. The canonical CODEC-CORTEX writer normalizes attrs and preserves cuerpo. }

LIM:no_cortex_write_for_governance{ limit:"Do NOT use cortex.write for governance files. Use project.init(seed=) and governance handlers.", severity:"blocking" }


$3: WRITER

KNW:writer{ tool:"write_cortex() via formats.py", behavior:"Uses CODEC-CORTEX CortexDocument -> write_cortex() for canonical output. Falls back to string builders if unavailable.", stems:"brain, manifest, meta-brain, projects, cycle, T-NNN" }
