$0

# -- $0: CORTEX SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Concept definition
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# STP   | step       | attrs      | M | Working        | How-to instruction
# KNW   | knowledge  | attrs      | B | Semantic       | Key knowledge
# OUT   | output     | attrs      | M | Working        | Output profile definition
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson
# FCS   | focus      | attrs      | H | Working        | Active attention anchor
# SES   | session    | attrs      | M | Episodic       | Session entry
# LIM   | limit      | attrs      | M | Prefrontal     | Hard constraint


$1: CANONICAL FORMAT RULES

AXM:attrs_single_line{ Attrs entries are written in ONE line. LNG:name{type:"process", lesson:"text"}. NO multiline with indentation. This maximizes information density for the LLM and avoids formatting errors. }

AXM:cuerpo_multiline{ Body entries (AXM, DESC) are written in multiline preserving literal text. The canonical CODEC-CORTEX writer normalizes attrs and preserves cuerpo. }

LIM:no_cortex_write_for_governance{ limit:"Do NOT use cortex.write for governance files. Use project.init(seed=) and governance handlers.", severity:"blocking" }

LIM:no_direct_edit{ limit:"Never edit governance files directly. Use MCP handlers.", severity:"blocking" }

AXM:extension_rule{ .cortex = state files (brain, manifest, tasks, cycles, identities). .md = agent bootstrapping files (AGENTS.md). Content defines format. cortex CLI parses CORTEX regardless of extension. No .md twins for .cortex files. }

AXM:memory_format{ While operating under Arqux governance, the agent's native memory MUST use CODEC-CORTEX content instead of prose. LNG in 30 tokens replaces 250 tokens of prose. Sigils are natural indices the LLM understands without a parser. }


$2: NATIVE AGENT MEMORY

IDN:native_memory{ principle:"If an LLM will read it, write it in CORTEX. Prose is only for direct human communication (AXM:natural_language).", density:"8x more information per token vs prose. Ultra-dense format with sigils that index content naturally for the LLM.", self_indexing:"Each entry has a sigil. scan FCS to know what matters, LNG to find lessons, SES to review history. No parser needed — sigils are natural indices." }

STP:memory_structure{
  structure:{
    FCS:current{ what:"What are we doing right now?", example:"FCS:adoption{what:'Arqux dogfooding', status:'active'}" },
    LNG:lessons{ what:"What have we learned?", example:"LNG:l001{type:'process', cause:'X', lesson:'Always Y'}" },
    KNW:knowledge{ what:"What stable knowledge do we have?", example:"KNW:patterns{domain:'auth', patterns:['oauth2','jwt']}" },
    SES:sessions{ what:"What happened in past sessions?", example:"SES:s01{cycle:'CYCLE-01', outcome:'done', date:'2026-07-06'}" },
  }
}

STP:memory_example{
  file:"alfred_memory.md (personal, NOT committed to repo)",
  content:"
$0
FCS:current{what:'Blueprint workflow design for Arqux', status:'active', project:'ARQUX'}
LNG:conversation{type:'process', lesson:'Architect prefers cyclic maturation before execution'}
SES:s01{cycle:'CYCLE-01', task:'BLP-001', outcome:'design', date:'2026-07-06'}
"
}


$3: AGENT INTERNAL FILES

AXM:cortex_for_internals{ Any file the agent writes for its own use (notes, plans, research, task tracking) MUST use CORTEX format. The benefits compound over sessions: what was learned in session N is immediately available to session N+1 via KNW entries. }

STP:internal_usage{
  notes:"Research notes about a technology → KNW:tech{domain:'OAuth2', patterns:[...]}. In 3 sessions you have a personal knowledge base.",
  plans:"Implementation plan → FCS:plan + OBJ:goals + STP:steps. Scan the plan in 10 tokens, not 200 words.",
  sessions:"Start: SES:sNN{status:'started'}. End: SES:sNN{status:'done', outcome:'...'}. Memory becomes a session log without bloat.",
  tasks:"Task tracking → FCS:current{what:'T-001', status:'in_progress'} + LNG:blockers{...}.",
}


$4: CORTEX-OUT OUTPUT PROTOCOL

IDN:cortex_out{ purpose:"Token-minimization output protocol. LLM responses contain a compressed sigil block (LLM-to-LLM context) plus optional natural language for the human reader.", profiles:"MIN (default), WORK, AUDIT, FULL, ERROR" }

OUT:MIN{ description:"One-line status. Use as default. ~10-30 tokens.", example:"OUT-MIN cycle=CYCLE-01 task=T-002 status=in_progress", when:"Default response. After every handler call." }

OUT:WORK{ description:"Operation result with evidence. ~50-100 tokens.", example:"OUT-WORK cycle=CYCLE-01 task=T-002 done=3 open=0", when:"After task.complete, task.fail, cycle.close, evidence.record" }

OUT:AUDIT{ description:"Full audit trail for a specific event. ~200 tokens.", example:"OUT-AUDIT event=E-0042 task=T-002 agent=jarvis kind=task_complete payload='tests pass'", when:"evidence.read with specific event_id. Auditor requests full detail." }

OUT:FULL{ description:"Complete state snapshot. ~300-800 tokens.", example:"OUT-FULL project=ARQUX cycle=CYCLE-01 tasks@SHORT agents=2", when:"project.status (verbose=true). workspace.status (verbose=true)." }

OUT:ERROR{ description:"Error with actionable hint. ~50 tokens.", example:"OUT-ERROR code=INVALID_STATE hint=close open tasks first", when:"Any handler returns an error. Always includes code + hint." }

STP:output_rules{
  include:"ALWAYS include the OUT-* sigil block. It IS the handler output. The natural language text that follows is supplementary context for humans.",
  language:"Natural language after the OUT-* block uses the working context language (AXM:natural_language).",
  minimal:"OUT-MIN is the default. Don't emit OUT-FULL unless explicitly requested.",
}


$5: KEY PRINCIPLES

AXM:density_over_prose{ Every token consumed by prose is a token NOT used for thinking. CORTEX delivers 8x the information per token. Write for the LLM reader, not the human reader. }

AXM:memory_evolves{ Agent memory is a living document. LNG entries accumulate. cortex.learn scans for patterns and proposes elevations to KNW. The agent's knowledge compounds over sessions. }

AXM:one_format_everywhere{ Governance state (.cortex), agent docs (AGENTS.md), skills (.skill.md), output (CORTEX-OUT), and agent memory (memory.md) — ALL use the same sigil format. The LLM learns the language once and applies it everywhere. }
