$0

# -- $0: LEARNING GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs-pos  | B | Semantic       | Concept definition
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Principle
# STP   | step       | attrs      | M | Working        | Procedure step
# POL   | policy     | attrs      | M | Prefrontal     | Policy / rule
# HDL   | handler    | attrs-pos  | M | Semantic       | MCP handler ref
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson
# SES   | session    | attrs      | M | Episodic       | Session episode
# KNW   | knowledge  | attrs      | B | Semantic       | Elevated knowledge

IDN:learning_framework{
  name:"ARQUX Learning Engine",
  purpose:"3-level learning: conductual → contextual → procedimental. Each level auto-feeds the next.",
  scope:"All governed projects. Lessons and knowledge are project-local unless elevated to meta-brain."
}

$1: ARCHITECTURE — 3-level learning

STP:levels{
  1_conductual:"identity.record → crea LNG en identidad del agente. Automatico al cerrar BLP o tarea.",
  2_contextual:"cortex.entry.add → agrega KNW en brain.cortex. Manual, para conocimiento estable del proyecto.",
  3_procedimental:"skill.edit → actualiza SKILL en .arqux/skills/. Para procedimientos repetibles que guian al agente.",
}
HDL:levels{identity.record, cortex.entry.add, skill.edit}

AXM:elevation_compounds{ Los 3 niveles se alimentan entre sí: (1) conductual repetido se eleva a contextual, (2) contextual validado por el Arquitecto se eleva a procedimental. }


$2: CLASSIFICATION — Inmediato

STP:classify_inmediato{
  1:"Al encontrar un patron o error: clasificar INMEDIATAMENTE en el nivel correcto:",
  "   CONDUCTUAL → identity.record (comportamiento del agente)",
  "   CONTEXTUAL → cortex.entry.add (conocimiento del proyecto)",
  "   PROCEDIMENTAL → skill.edit (workflow o procedimiento)",
  2:"NO esperar a tener los 3 niveles. Guardar donde corresponda ahora.",
  3:"La elevación (SES→LNG→KNW→SKILL) es POSTERIOR — no detener el trabajo actual para elevacion.",
}
HDL:classify{identity.record, skill.edit}

AXM:classify_now{ Clasificar inmediatamente al detectar. NO guardar como memoria ni esperar a tener los 3 niveles completos. }

AXM:knw_self_contained{ Al consolidar LNG → KNW, eliminar los LNG fuente. El KNW debe ser auto-suficiente: contener toda la informacion que los LNG individuales cubrian, sin requerir que el lector recurra a los entries originales. Mantener LNG detallados + KNW compacto = inflacion de tokens. KNW reemplaza, no complementa. }


$3: ELEVATION — SES → LNG → KNW

STP:elevation_pipeline{
  1:"SES → LNG (auto): cierre de sesion via session.close() genera LNG candidate.",
  2:"LNG → KNW (propuesta): cortex.learn escanea y propone cuando promotion_score >= 8.",
  3:"KNW → SKILL (manual): Arquitecto decide si conocimiento consolidado merece skill propio.",
  4:"LNG → KNW manual (alternativa): CortexWrite directo para consolidacion inmediata. Siempre eliminar LNG fuente tras consolidar."
}
HDL:elevation{cortex.learn.elevate}

AXM:elevation_auto{ La elevacion automatica requiere recurrencia entre sesiones. Lecciones de una sola sesion NO son candidatas hasta que reaparezcan. }

POL:promotion_thresholds{ses:1, lng:3, knw:8, auto_knw:13}
POL:cooling{half_life_days:7, min_score_to_survive:1}
POL:detection{same_sigil_in_window:3, window_hours:72, cross_session:true}
POL:auto_ses_to_lng{when:"promotion_score>=8|user_validated=true", action:"apply"}
POL:auto_lng_to_knw{when:"promotion_score>=13|user_validated=true|risk_weight>=8", action:"apply", requires:"admin_policy"}


$4: EXCEPTIONS — Elevation from placeholders

AXM:no_elevate_placeholders{ NO elevar entries con campos placeholder o default (risk=pending, mitigation=pending, cause=not_specified, prevention=not_applicable). La elevacion desde datos genericos produce KNW sin valor semantico. Solo entries con contenido real y recurrencia entre sesiones merecen elevation. }

LNG:elevation_placeholders{type:"contextual", cause:"cand_001/002 rejected by Architect — RSK/WRK placeholders produjeron CNST/SES generica sin valor", lesson:"No elevar entries con valores placeholder. La elevacion desde datos semanticamente vacios produce conocimiento vacio. Verificar contenido real antes de proponer."}


$5: CONSOLIDATION — LNG → KNW manual

STP:consolidate_manual{
  1:"Identificar LNGs relacionados por topico (revisar brain.cortex $7)",
  2:"Agrupar en clusters semanticos (handler rules, architect comm, infra, etc.)",
  3:"Redactar KNW auto-suficiente que resuma TODOS los LNGs del cluster",
  4:"ESCRIBIR KNW en brain.cortex $10 via cortex.entry.add o write directo",
  5:"ELIMINAR los LNGs fuente de $7 (ya no son necesarios)",
  6:"Verificar: el KNW cubre la informacion sin requerir los LNG originales",
  key_rule:"KNW auto-suficiente: no mantener LNG detallados como 'respaldo'. KNW reemplaza, no complementa. Reduccion de tokens es el objetivo.",
}
