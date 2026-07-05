$0

# -- $0: CORTEX-OUT SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Profile definition
# DESC  | description | cuerpo     | B | Semantic       | Profile description


$1: PROFILES

IDN:profiles{ profiles:"OUT-MIN, OUT-WORK, OUT-AUDIT, OUT-FULL, OUT-ERROR", rule:"Pick the smallest profile that conveys the information." }

DESC:out_min{ Quick status acks, no detail needed. Example: "OK T-001 in_progress" }

DESC:out_work{ Work updates, deliverables, evidence. Example: "DONE T-001 evidence=E-007" }

DESC:out_audit{ Architecture reviews, decisions. Example: "REVIEW cycle=CYCLE-01 risk=low" }

DESC:out_full{ Detailed explanations to the Architect in natural language. }

DESC:out_error{ Failures, blockers, permission denials. Example: "ERROR code=NOT_FOUND" }


$2: PREFIX

IDN:prefix{ format:"<sigil>[<project>|<agent>]", example:"OUT-WORK ENVX_OPER|alfred", purpose:"Every response is prefixed with CORTEX-OUT profile + agent context." }
