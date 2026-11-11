# Evaluación transversal de ArqUX — SES017 (CYCLE-15)

> Documento autónomo del loop A–H, mandato del Arquitecto 2026-11-02.
> Cuatro identidades con su contrato fijado y handoff registrado en la sesión
> (`identity-switch` → PULSE + `.arqux/handoffs/<agente>.cortex`).

---

## Alfred — gobernador (autor del loop)

**Virtudes.** El axioma brain-first + WRK:current funciona: SES017 sobrevivió un
reinicio del cliente, se re-adhirió y continuó sin pérdida. El modelo de tres
niveles de aprendizaje (conductual→identidad, contextual→brain,
procedimental→skill) ya está implementado en código y tests, no solo en papel.
La gobernanza por handlers con validación previa evitó que el writer volviera a
corromper un contrato — y esta sesión eliminó la causa raíz (GSIG descartado en
el parse fallback).

**Defectos.** La superficie de handlers es potente pero opaca: los errores
devuelven el catálogo completo y cada INVALID_ARGS es una ronda perdida. Los
hooks de formato (§14 checklist) se verifican tarde. El glosario `$0` queda
fuera del CRUD — la única vía es reescritura total. CODEC-CORTEX 0.6.x instalado
vs 1.0 local gobernado: la adopción de v1.0 exige portar validate /
render_hcortex_read / crud.selectors, aún sin decidir (BLP-021).

## Heimdall — auditor

Veredicto CONFORME sobre BLP-020 con cuatro hallazgos: H-01 sin ruta MCP para
mutar el glosario (medio, issue registrado); H-02 GSIGs ausentes en 6/7
identidades del workspace (bajo, se autoresuelve con la ruta sancionada); H-03
lock residual (higiene); H-04 harness de conformidad referencia un archivo
externo ausente en el proyecto v1.0 (ambiental, alimenta BLP-021).

**Lectura del sistema.** Las guardas funcionan en capas (destino → E023 →
filtro) y cada capa ahora tiene su test. Recomendación de endurecimiento:
auditar periódicamente que `filter_dialect_false_positives` no crezca —
cada exención es una deuda que paga el validador.

## Jarvis — ejecutor

El ciclo claim→update→complete con evidencia es real y auditable; la suite de
2596 tests da confianza. Defectos de trinchera: esquemas de handlers rígidos con
errores masivos (mortal en tier LITE), validación de formato tardía en
blueprints, `$0` fuera del CRUD, y desconexión entre tareas §14 y `task_id` de
evidence.record. Propuestas: errores compactos (código + enum + ejemplo),
validación temprana en blueprint.update, ruta de glosario, puente BLP-task↔task.

## Seshat — escriba

La memoria CORTEX es legible por humanos y máquinas; el header hace la identidad
explícita; las skills son artefactos versionados. Defectos: divergencia
contratos↔templates (glosario por comentarios vs ejecutable — dos formatos sin
canon), skills duplicadas workspace↔src sin fuente de verdad única, y narrativa
del framework dispersa (AGENTS, issues, blueprints, brains) sin documento de
arquitectura canónico. Propuestas: canonizar formato de identidad, skill única
publicada desde src/, `docs/arquitectura.md` curado.

---

## Síntesis y ajustes propuestos

| # | Ajuste | Origen | Estado |
|---|---|---|---|
| 1 | Ruta MCP para mutar glosario `$0` | Heimdall/Jarvis | issue `2026-11-02-sin-ruta-mcp-para-mutar-el-glosario` |
| 2 | Errores de handler compactos (código+enum+ejemplo) | Jarvis | issue `2026-11-02-errores-de-handler-verbose-vuelca` |
| 3 | Adopción codec-cortex v1.0 | Alfred | BLP-021 (draft) |
| 4 | Canonizar formato de identidades + skills única fuente | Seshat | propuesta, pendiente BLP |
| 5 | docs/arquitectura.md canónico | Seshat | propuesta, pendiente BLP |
| 6 | Puente tareas §14 ↔ task_id | Jarvis | propuesta, pendiente BLP |

## Aprendizajes generales

1. **La exención gobernada es más barata que la corrupción.** La ruta sancionada
   de lecciones conductuales costó una exención acotada + un filtro E023 +
   declaración de glosario; el camino no sancionado costó 195KB y un barrido.
2. **El formato CORTEX paga en recuperación.** Toda la reanudación (brain,
   checkpoints, pending_loop) es parseo declarativo — ningún mecanismo depende
   de memoria de proceso.
3. **El loop autónomo necesita un evento, no solo un marcador.** WRK:current
   solo se lee cuando alguien arranca; `context_set` ahora superficia
   `pending_loop`, convirtiendo el bootstrap en el disparador.
4. **Los tests son el segundo contrato.** Cada hallazgo (E023, GSIG, sesión,
   loop) terminó como test; sin ellos la suite no habría confirmado delta-0.
