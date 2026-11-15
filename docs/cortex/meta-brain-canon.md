# Canon — `meta-brain.cortex` (Nivel 3 / META-BRAIN del workspace)

**Estado:** canon vigente aplicado al scope workspace (ALFRED ·
CYCLE-16 · 2026-11-15).
**Alcance:** `<workspace>/.arqux/meta-brain.cortex` — la memoria del
workspace: proyectos gobernados, agentes, foco transversal. NO es el
brain de un proyecto: el workspace es contenedor (`AXM:no_workspace_project`).

---

## 1. Qué es

La memoria *inter-proyecto*: qué proyectos gobierna el workspace, qué
agentes operan, el foco transversal del Arquitecto. Misma filosofía
GRADIENT que `brain-canon.md` — `$N` = distancia a la verdad — con la
sustitución de scope: proyecto → workspace.

## 2. Layout vigente (post-migración G-8, 2026-11-15)

El archivo YA migró al layout canónico — 38 entradas, `cortex_verify`
valid=true:

| # | Título | Zona | Contenido real |
|---|---|---|---|
| $0 | `GLOSSARY` | envelope | `$0:format` + contratos (`FCS`/`KNW`/`OBJ`/`WRK` añadidos en la reparación; `cortex_verify` reporta I001 informativo de auto-adición — verificable vía handler) |
| $1 | `IDENTITY` | contract | `ARQX:artifact{level:3}` + `IDN:workspace{name, root, governor, projects:"18", status:"current"}` |
| $2 | `AXIOMS` | contract | vacía — constitución del workspace pendiente de sembrar |
| $3 | `KNOWLEDGE` | contract | verdad transversal operativa |
| $4 | `RISKS` | contract | vacía |
| $5 | `FOCUS` | state | `FCS:current` |
| $6 | `OBJECTIVES` | state | `OBJ:workspace` |
| $7 | `ACTIVE_CONTEXT` | state | **`WRK:current{name:"workspace", project:"ARQUX", scope:"CYCLE-16", agent:"Alfred", ses:"SES021", project_root}`** — absorbió `context.cortex` |
| $8 | `LESSONS` | staging | vacía — regla vigente: lecciones solo en brain `$8` del proyecto origen |
| $9 | `LOOPS` | system | vacía |
| $10 | `REGISTRY` | system | `DOM:*` proyectos (18 — cero `PRJ:`; `PRJ` es el sigilo de projections del timelog) + `IDN:*` agentes (7: alfred, jarvis, heimdall, seshat, auditor, executor, governor) |

### 2b. Layout histórico (pre-G-8)

`$1 META-BRAIN · $2 PROJECTS · $3 FOCUS · $4 AGENTS · $5 KNOWLEDGE`
+ `$19 ARQUX METADATA`. Migrado físicamente el 2026-11-15; otros
proyectos gobernados pueden seguir en este layout (migración
workspace-wide pendiente).

## 3. Defectos resueltos en la reparación (audit Heimdall)

- `DOM:domain` (residuo de registry) — eliminado.
- `IDN:new-agent` (residuo de `agents.cortex`) — eliminado.
- Registry de agentes completado: 7 `IDN` (antes solo 2).
- `$0` completado: `FCS`/`KNW`/`OBJ`/`WRK` declarados.
- Residuo abierto (I002 del verificador): 5 placeholders en 4
  entradas — `IDN:workspace{root:"<workspace-root>", created:"<timestamp>"}`,
  `FCS:current{updated:"<timestamp>"}`, `IDN:alfred`/`IDN:jarvis`
  `{adopted:"<timestamp>"}` — se resuelven en la próxima escritura
  legítima.

## 4. Reglas heredadas del canon brain

1. Mismo principio de composición (`brain-canon.md` §1.3) — toda
   propuesta de dato pasa la prueba.
2. `ARQX:artifact` cabecera de `$1` con `version`/`revision`/
   `last_writer`.
3. Eventos: ninguno — el workspace no produce eventos de sesión
   (viven en timelogs de proyectos).
4. Resolución por título; mutación solo por handlers MCP.

## 5. Referencias

- `brain-canon.md` — el canon madre (GRADIENT-12)
- `migration.md` G-6 — aplicación física de este layout
- `artifacts.md` §2.1 — ficha nivel 3 workspace
