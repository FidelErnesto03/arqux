$0

# -- $0: MEMORY SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Memory rule
# LNG   | lesson     | attrs      | M | Episodic       | Example entry
# KNW   | knowledge  | attrs      | B | Semantic       | Example entry
# FCS   | focus      | attrs      | H | Working        | Example entry
# SES   | session    | attrs      | M | Episodic       | Example entry


$1: PRINCIPLE

AXM:memory_format{ While operating under Arqux governance, the agent's native memory (memory.md, user.md, or equivalent) MUST use CODEC-CORTEX content instead of prose. Rationale: extreme information density. A LNG entry in 30 tokens replaces 250 tokens of prose. Sigils are natural indices the LLM understands without a parser. }


$2: RULES

STP:1{ action:"Keep the memory file name and extension (.md)", note:"Only the content changes, not the file." }
STP:2{ action:"Content uses CORTEX sigil format with $0 glossary", note:"Refer to format.skill.md for canonical formatting." }
STP:3{ action:"Write LNG (lessons), KNW (knowledge), FCS (focus), SES (sessions) directly in memory", note:"These are the most information-dense sections." }
STP:4{ action:"On session start, scan LNG and KNW as priority context load", note:"These sections contain the most valuable cross-session information." }


$3: EXAMPLES

LNG:example{ type:"process", cause:"Handlers without path failed with NOT_FOUND", lesson:"Always pass explicit path to discovery handlers." }

KNW:example{ topic:"project-architecture", content:"The codec uses CortexDocument -> write_cortex() for canonical output. Attrs single-line, cuerpo multiline." }

FCS:example{ what:"Complete the L-016 refactor — make write_cortex the default writer for all .cortex files", priority:"high", status:"current" }

SES:example{ input:"Session start with Architect to review state", output:"Adoption L-016 completed, 57 tests green", role:"governor", outcome:"ok", date:"2026-07-05" }
