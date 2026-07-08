$0

# -- $0: WORKFLOW W03 —
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# DIAG  | diagram    | cuerpo     | B | Semantic       | PlantUML diagram
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule

IDN:w03{ name:"Session Start", purpose:"Agent startup in a governed workspace. Presents context from brain.cortex at the appropriate level.", trigger:"Agent starts in a governed workspace." }

AXM:session_context_first{ The FIRST response in a governed workspace MUST include context from brain.cortex. The response level depends on where the agent is in the workspace tree. }

DIAG:w03{
@startuml
actor "Arquitecto" as A
participant Agent as G
database "brain.cortex" as BC
database "AGENTS.md" as AG

G -> AG: Read AGENTS.md
note right: PHASE 0: detect .arqux/

G -> G: Verify ARQUX_AGENT_ROLE
note right: Must be governor for write access

alt Workspace root (no project selected)
    G -> BC: Read meta-brain.cortex
    G --> A: List projects with status + description
else Inside a project
    G -> BC: Read brain.cortex (FCS, OBJ, LNG)
    G --> A: Project + cycle + blueprints status
else Inside a cycle
    G -> BC: Read cycle MANIFEST.md
    G --> A: Cycle manifest + all blueprints with status
end

G --> A: Open question — what to work on?
@enduml
}

STP:w03_s{
  1:"Verify ARQUX_AGENT_ROLE — report if auditor/empty",
  2_workspace_level:"List projects from meta-brain: name, last active, status. Ask which to work on.",
  3_project_level:"Read brain.cortex: project, active cycle, blueprints (count + status). Present in HCORTEX.",
  4_cycle_level:"Read MANIFEST.md: objectives, blueprints with status, next control point.",
  5_format:"HCORTEX vertical layout with one-line summary + open question.",
  key_rule:"Context before conversation. Never just a greeting.",
}
