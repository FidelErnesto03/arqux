$0

# -- $0: LEARNING SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Feature definition
# KNW   | knowledge  | attrs      | B | Semantic       | How it works
# STP   | step       | attrs      | M | Working        | Usage step
# FCS   | focus      | attrs      | H | Working        | When to use
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference


$1: WHAT IT IS

IDN:learning_engine{ name:"CODEC-CORTEX Learning Engine (CLE)", type:"adapter", location:"learning.py", handler:"cortex.learn", purpose:"Deterministic learning engine that scans brain.cortex, detects patterns in repeated lessons, and proposes elevations from LNG (lessons) to KNW (permanent knowledge)." }

KNW:how{ content:"The engine uses configurable Fibonacci policies in .arqux/learn-policies.cortex. It scans LNG, SES, WRK, RSK entries and computes 4 scores: hotness (recurrence), promotion (elevation fitness), risk (cost of losing the entry), read_priority (P0-P5). When 3+ similar lessons appear, it detects a pattern and proposes elevation to KNW." }


$2: WHEN TO USE

FCS:trigger{ when:"After closing a cycle", reason:"Natural moment: all cycle tasks complete, evidence accumulated" }
FCS:trigger{ when:"When the Architect asks 'what have you learned'", reason:"Scan provides concrete data and candidates" }
FCS:trigger{ when:"Before starting a new phase", reason:"Previous phase lessons become permanent knowledge" }
FCS:trigger{ when:"Periodically, when many unprocessed AUDs exist", reason:"Engine detects patterns the agent might miss manually" }


$3: HANDLERS

HDL:cortex.learn{ signature:"learn(scope?, path?)", purpose:"Escanea brain.cortex, ejecuta scoring completo, retorna candidatos a elevacion. scope=workspace incluye candidatos detallados." }

HDL:cortex.learn.elevate{ signature:"learn.elevate(candidate_id, apply?, path?)", purpose:"Eleva un candidato. Por defecto dry-run (solo muestra el diff). apply=true escribe la elevacion en brain.cortex." }


$4: USAGE FLOW

STP:1{ action:"cortex.learn(path='./project')", result:"Returns N scanned entries and M detected candidates", note:"Engine must be 'available'. If 'unavailable', codec-cortex lacks the learning module." }
STP:2{ action:"Review candidates", result:"Each candidate shows source, target, promotion_score and hotness_score", note:"An LNG with hotness=5 and promotion=5 means 3+ similar lessons → pattern detected" }
STP:3{ action:"cortex.learn.elevate(candidate_id='cand_001', path='./project')", result:"Shows diff without applying (dry-run)", note:"Always dry-run first to verify the change is correct" }
STP:4{ action:"cortex.learn.elevate(candidate_id='cand_001', apply=true, path='./project')", result:"Writes elevation to brain.cortex: LNG preserved in LESSONS, new KNW appears in KNOWLEDGE" }
STP:5{ action:"Verify: task.read or other handler confirms brain is updated", result:"KNOWLEDGE section with new content" }


$5: POLICIES

KNW:policies{ content:"Policies are in .arqux/learn-policies.cortex. Copied during workspace.init and project.init. The Architect can edit them directly to adjust Fibonacci thresholds (1,2,3,5,8,13,21), protected sigils, or elevation rules. No code changes required." }

STP:customize{ 1:"Edit .arqux/learn-policies.cortex", 2:"Adjust THR:golden_fibonacci{...}", 3:"For example: change candidate:5 to candidate:3 to be more sensitive", 4:"cortex.learn will use the new thresholds automatically" }
