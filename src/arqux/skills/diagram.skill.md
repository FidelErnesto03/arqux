$0

# -- $0: DIAGRAM SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Skill identity
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# STP   | step       | attrs      | M | Working        | Procedure step
# CHK   | checklist  | attrs      | M | Protocol       | Validation checklist
# PFL   | pitfall    | contenido  | M | Episodic       | Known error
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference


$1: DIAGRAM PROTOCOL (3 PHASES)

IDN:diagram_skill{ name:"Diagram Production Protocol", purpose:"Create, validate, and publish PUML diagrams for HCORTEX documents. 3-phase protocol adapted from DIALECT v5.5.", version:"1.0.0", tags:["arqux","puml","plantuml","diagram","validation"] }


$2: PHASE 1 — CONSULT AND CREATE

STP:phase1{
  1:"Identify what the diagram needs to express: architecture, sequence, state, or context.",
  2:"If syntax reference needed: consult PlantUML guide or existing Arqux diagrams (BLP-001, workflows.skill.md).",
  3:"Write the PUML following Arqux conventions (see §5).",
  output:"PUML block ready for validation.",
}

AXM:approved_types{ Allowed: sequence, activity, class, state, usecase, component, deployment. Prohibited: mindmap, gantt, wireframe, ditaa, nwdiag. }

AXM:metadata_required{ Every PUML block MUST include a metadata header as comments before @startuml: @name, @description, @category, @tags, @version. }


$3: PHASE 2 — VALIDATE

STP:phase2{
  1:"Run validation: cortex.render.diagram(source, format='svg').",
  2:"If syntax error → fix and re-validate.",
  3:"Apply checklist D1-D5 (see §6).",
  4:"Repeat until all checks pass.",
}

AXM:validate_before_use{ NEVER embed a PUML diagram in a BLP or HCORTEX document without validating it first. Unvalidated diagrams cause render errors that block document review. }


$4: PHASE 3 — PUBLISH

STP:phase3{
  1:"Embed the validated PUML in the target BLP section (§5, §8, §9).",
  2:"Ensure the PUML block is the PRIMARY expression — prose is supplementary.",
  3:"If the diagram replaces a previous version, update @version in metadata.",
}

AXM:puml_as_spec{ PUML diagrams are executable specifications, not illustrations. An agent should be able to follow a sequence diagram like a script. Text outside PUML should be ≤10% of the section content. }


$5: PUML CONVENTIONS

AXM:naming{ diagram_name format: blp_NNN_section_N_description. Example: blp_001_s5_create_flow, blp_006_s5a_session_close. }

AXM:prohibited_directives{ DO NOT use: skinparam global, box, newpage, autonumber, skinparam monochrome. Use inline styling if absolutely necessary. }

AXM:delimiters{ Every PUML block MUST have matching @startuml and @enduml. Missing delimiters cause parse failures. }

AXM:text_ratio{ Text outside PUML blocks in diagram sections should be ≤10%. If you need paragraphs to explain the diagram, the diagram is incomplete. }


$6: VALIDATION CHECKLIST (D1-D5)

CHK:d1_delimiters{ check:"@startuml and @enduml present and matching", action:"Add missing delimiters" }

CHK:d2_metadata{ check:"Metadata header present: @name, @description, @category, @tags, @version", action:"Add missing metadata fields" }

CHK:d3_syntax{ check:"cortex.render.diagram() returns OK", action:"Fix syntax errors reported by PlantUML parser" }

CHK:d4_semantic_flow{ check:"Arrows and decisions express the complete process. No dead ends without explanation.", action:"Add missing transitions or notes" }

CHK:d5_no_prohibited{ check:"No skinparam global, box, newpage, autonumber, mindmap, gantt, wireframe", action:"Remove prohibited directives" }

CHK:t1_text_ratio{ check:"Text outside PUML ≤10% of section content", action:"Move explanatory text INTO the diagram as notes or reduce prose" }

CHK:t2_no_duplicate_narrative{ check:"No prose paragraphs that describe the same flow already shown in the diagram", action:"Remove duplicate narrative — the diagram IS the specification" }


$7: HANDLERS

HDL:cortex_render_diagram{ handler:"cortex.render.diagram", description:"Validate and render PUML to SVG/PNG. Use for individual diagram validation during Phase 2.", risk:"M" }

HDL:cortex_render{ handler:"cortex.render", description:"Render entire .cortex file to HCORTEX. Validates all embedded PUML blocks in batch.", risk:"M" }

HDL:arqux_render_diagram{ cli:"arqux render-diagram <file.puml> --format svg", description:"CLI fallback for diagram validation without MCP.", risk:"L" }


$8: PITFALLS — KNOWN FAILURES

PFL:p01_note_on_action_line{ error:"note right on same line as action causes parse failure", example:"Agent -> Agent: do something note right: text", fix:"Always put note on its OWN line after the action.", severity:"HIGH" }

PFL:p02_multiline_note_no_end{ error:"Multi-line notes without end note fail in PlantUML < 1.2025", example:"note right: line1\\nline2\\nline3", fix:"Use single-line notes or add explicit end note block.", severity:"HIGH" }

PFL:p03_unicode_arrows{ error:"Unicode arrow (→) in message text causes parse failure", example:"Agent -> BC: read → adopt", fix:"Replace with ASCII text: 'leer y adoptar'.", severity:"MEDIUM" }

PFL:p04_backslash_n_in_names{ error:"Literal backslash-n (\\n) in participant names fails", example:'participant "Alfred\\n(session)"', fix:"Use spaces: 'Alfred (session)'. No \\n in participant names.", severity:"HIGH" }

PFL:p05_multiline_message{ error:"Message text split across multiple lines without continuation causes parse failure", example:"A -> B: line1\\nline2", fix:"Keep each message on a SINGLE line. Combine long text with commas.", severity:"MEDIUM" }

PFL:p06_nested_repeat{ error:"repeat/repeat while blocks nested 3+ deep cause failure in PlantUML < 1.2025", fix:"Use while/endwhile (newer) or simplify to max 2 nesting levels with repeat.", severity:"HIGH" }

PFL:p07_bullets_in_notes{ error:"Bullet points (-, *) in note right cause failure in PlantUML < 1.2025", example:"note right: - item1\\n- item2", fix:"Use commas: 'item1, item2, item3'. No bullet characters in notes.", severity:"MEDIUM" }

PFL:p08_special_chars_in_names{ error:"Special characters (parentheses, colons, newlines) in participant/actor names cause failure", fix:"Use simple ASCII names. Add detail in message text, not participant names.", severity:"MEDIUM" }

PFL:p09_standalone_text{ error:"Text outside of any actor/message/note in sequence diagram causes failure", example:"A -> B: message\\n¿question?", fix:"All text must be part of a message, note, or divider (==). No standalone lines.", severity:"HIGH" }


$9: CONSTRUCTION RULES — BUILD CORRECTLY FROM START

AXM:one_line_per_element{ Every PlantUML element (message, note, action, participant) must be on its OWN line. Never put two elements on the same line. }

AXM:notes_after_actions{ Notes always go on the line AFTER the action they describe. Never on the same line. Keep notes to one line. }

AXM:ascii_only{ Use only ASCII characters in diagram text. No Unicode arrows, no special quotes, no em dashes. Replace → with 'to', replace ¿ with regular text. }

AXM:simple_names{ Actor and participant names: ASCII only, no newlines, no parentheses. Maximum 30 characters. }

AXM:one_message_per_line{ Each message arrow (->, -->, ->o) must fit on a SINGLE line. If the message text is too long, shorten it. Never split across lines. }

AXM:max_nesting_2{ Diagram nesting (repeat, if/else, while) must not exceed 2 levels deep. If you need more, restructure the diagram or split into multiple diagrams. }

AXM:validate_before_embed{ Before embedding any PUML block in a BLP or HCORTEX document, run cortex.render.validate_file on it. Fix all errors before presenting to the Architect. }


$9: EXAMPLES

IDN:canonical_diagrams{
  create_flow:"BLP-001 §5a — activity diagram with partitions, execute_flow_phases",
  execute_flow:"BLP-001 §5b — activity diagram with task loop and AC validation",
  operational:"BLP-001 §8 — sequence diagram with 5 phases and explicit handler calls",
  technical:"BLP-001 §9 — component diagram with 3 handlers and BLP document",
  state_machine:"workflows.skill.md §8 — state transition diagram for Blueprint lifecycle",
}
