$0

# -- $0: RE WORKFLOW SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow identity
# STP   | step       | attrs      | M | Working        | State transition
# GATE  | gate       | attrs      | H | Prefrontal     | Quality contract gate
# FCS   | focus      | attrs      | H | Working        | Current next action
# DESC  | description | cuerpo     | B | Semantic       | State description


$1: IDENTITY

IDN:re_workflow{ name:"RE Maturation + Execution Workflow", version:"1.0", purpose:"Define el ciclo completo de una RE desde su creacion hasta su cierre, incluyendo el contrato de maduracion (6 gates) que debe cumplirse antes de la ejecucion.", source:"Inspired by DIALECT v5.5 RE lifecycle, adapted for Arqux governance." }

DESC:overview{ Cada RE (Requerimiento Especifico) pasa por 3 fases: MADURACION (gates must pass), EJECUCION (task claimed and worked), CIERRE (evidence + lessons). En cada estado, el skill dice al agente cual es el siguiente paso. El agente NO memoriza el flujo — carga este skill y sigue la instruccion STP para el estado actual. }


$2: RE STATES AND TRANSITIONS

FCS:states{
  draft:"RE creada, OBJ basico definido. Gates sin completar.",
  defined:"OBJ + scope + mandatory rules definidos. Listo para maduracion.",
  maturing:"El agente completa los 6 gates uno por uno. No se ejecuta nada.",
  ready:"Todos los gates pasaron. Governor puede asignar executor.",
  in_progress:"Executor reclamo la RE. Trabajo en curso.",
  blocked:"La RE encontro un obstaculo. Se reporta al governor.",
  review:"Trabajo completado. Governor o auditor revisa.",
  done:"RE cerrada con exito. Evidencia + lecciones registradas.",
  cancelled:"RE cancelada. Motivo documentado.",
}

STP:transitions{
  valid:"draft→defined→maturing→ready→in_progress→review→done",
  alt:"in_progress→blocked→maturing (re-plan)",
  terminal:"done, cancelled",
}


$3: QUALITY CONTRACT (6 GATES)

AXM:quality_gates{ Antes de que una RE pase de maturing a ready, TODOS los gates deben ser true. Si algun gate es false, la RE sigue en maturing. El agente carga este skill y revisa cada gate contra el estado actual de la RE. }

GATE:objective{ field:"has_clear_objective", question:"Is the objective concrete, verifiable, and self-contained? Can an executor understand what to do without extra explanation?", next_step:"If false: task.update(task_id, note='Refining objective') → return to defined" }

GATE:preconditions{ field:"has_verifiable_preconditions", question:"Are all preconditions listed and verifiable via command or inspection? Can the executor confirm each one before starting?", next_step:"If false: ask governor for preconditions clarification" }

GATE:scope{ field:"has_scope_and_exclusions", question:"Is the scope explicitly defined? What is OUT of scope? Are boundaries clear?", next_step:"If false: add §5 Scope section to RE body" }

GATE:acceptance{ field:"has_acceptance_criteria", question:"Are there 2+ acceptance criteria (AC-01, AC-02...)? Is each AC verifiable with a concrete command or procedure?", next_step:"If false: add AC entries with verification commands" }

GATE:procedure{ field:"has_work_procedure", question:"Is there a step-by-step procedure the executor can follow? Are phases defined with rollback instructions?", next_step:"If false: define phases, steps, and rollback in §10 Work Procedure" }

GATE:validations{ field:"has_required_validations", question:"Are required validations listed with commands? (test, lint, security, integration)", next_step:"If false: add at least 3 validation entries to §12 Required Validations" }


$4: STATE GUIDANCE — WHAT TO DO AT EACH STATE

FCS:draft{ description:"RE recien creada con OBJ. Necesita ser definida.", next_action:"task.define(task_id, pre=[...], scope='...', ac=[...], mandatory_rules=[...])", next_state:"defined", skill_action:"Load re-workflow.skill.md → read §4 draft → follow next_action" }

FCS:defined{ description:"RE tiene estructura basica. Lista para maduracion.", next_action:"task.mature(task_id) → state changes to maturing. Agent starts reviewing gates.", next_state:"maturing", skill_action:"Load re-workflow.skill.md → read §3 Quality Contract → review each gate against task content" }

FCS:maturing{ description:"Agente completa gates uno por uno. Cada gate completado → task.update(task_id, note='Gate X passed').", next_action:"Check each of the 6 GATEs. When all are true, call task.ready(task_id).", next_state:"ready", skill_action:"Load re-workflow.skill.md → read §3 GATE entries → for each gate, check value, take action if false" }

FCS:ready{ description:"RE lista para ejecucion. Governor asigna executor.", next_action:"Governor: task.assign(task_id, executor='agent_id'). Executor: task.claim(task_id).", next_state:"in_progress", skill_action:"Governor loads re-workflow.skill.md → verifies all gates passed → assigns executor" }

FCS:in_progress{ description:"Executor trabajando en la RE.", next_action:"Periodicamente: task.update(task_id, note='progress'). Al completar hitos: evidence.record(kind='artifact', payload=...).", next_state:"review (o blocked si hay obstaculo)", skill_action:"Executor loads re-workflow.skill.md → follows §5 execution cycle" }

FCS:blocked{ description:"RE encontro un obstaculo.", next_action:"task.fail(task_id, reason='...'). El governor evalua: re-plan o cancel.", next_state:"maturing (re-plan) o cancelled", skill_action:"Governor loads re-workflow.skill.md → §4 blocked → decide re-plan or cancel" }

FCS:review{ description:"Trabajo completado. Revisar evidencia.", next_action:"Governor/auditor: verificar evidencia contra acceptance criteria. task.complete(task_id) si pasa.", next_state:"done", skill_action:"Auditor loads re-workflow.skill.md → §4 review → valida cada AC contra evidencia" }

FCS:done{ description:"RE cerrada con exito.", next_action:"Registrar lecciones en brain: identity.record(lesson='...'). cycle.close si todas las RE estan done.", next_state:"(terminal)", skill_action:"Agent loads re-workflow.skill.md → §4 done → records lesson via identity.record()" }

FCS:cancelled{ description:"RE cancelada.", next_action:"Documentar motivo. Evaluar si se necesita reemplazo.", next_state:"(terminal)", skill_action:"Governor loads re-workflow.skill.md → §4 cancelled → evaluates replacement" }


$5: EXECUTION CYCLE

STP:execution_cycle{
  1:"Load this skill to know what to do at current state",
  2:"Execute the next_action described for your state",
  3:"Record evidence: evidence.record(kind='artifact', payload=...)",
  4:"Periodically: task.update(task_id, note='what was done')",
  5:"On completion: task.complete(task_id, evidence='...')",
  6:"On obstacle: task.fail(task_id, reason='...') → governor re-evaluates",
}


$6: HOW THE AGENT USES THIS

STP:agent_usage{
  1:"Receive task assignment (T-001)",
  2:"Load this skill: skill_view('re-workflow')",
  3:"Check current state: task.read(T-001) → frontmatter.status",
  4:"Go to §4, find the FCS entry for your current state",
  5:"Execute the next_action described there",
  6:"Report result to the governor/architect",
  repeat:"After each state change, reload the skill and follow the new state's guidance",
}


$7: INTEGRATION WITH TASK HANDLERS

KNW:handlers_needed{ list:"task.create, task.read, task.update, task.claim, task.complete, task.fail, task.mature?, task.ready?", note:"task.mature and task.ready are proposed new handlers. task.create/claim/complete/fail already exist.", rationale:"task.mature changes status to maturing and initiates gate checking. task.ready changes status to ready (all gates passed)." }

KNW:handler_evolution{ note:"Current handlers (task.create, task.claim, task.complete, task.fail) remain unchanged. New handlers (task.mature, task.ready, task.assign) extend the lifecycle without breaking existing workflows.", compatibility:"Backward compatible: existing cycles still work with draft→open→in_progress→done flow. New cycles can use the full maturation flow." }
