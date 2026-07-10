# diagnostico-niveles.hcortex.md
> Blueprint: BLP-034
> Gobernador: alfred
> Executor: jarvis
> Fecha: 2026-07-10
> Estado: GAP_MAP_COMPLETADO

---

$0: METADATA
IDN:diagnostico-niveles{type:"hcortex-gap-map", version:"1.0.0", cycle:"CYCLE-01"}
WRK:blp-034{status:"completed", result:"7 gaps identificados"}

---

# RESUMEN EJECUTIVO

El diagnóstico revela una **desincronización crítica** entre la especificación teórica v3.0 (`docs/niveles-cortex-arqux.md`) y la implementación actual en el código fuente (`src/arqux/`). 

El framework carece de la **Capa de Validación de Niveles** requerida. Aunque la estructura de archivos y persistencia (`state.py`, `handlers/`) soporta la lectura y escritura básica de `.cortex`, no existe gobernanza semántica sobre los niveles 0, 1, 2 y 3. Esto permite la creación de estados inválidos (ej. brains sin foco activo) y rompe el principio rector: *"La documentación es la fuente de verdad"*.

---

# 1. MATRIZ DE CORRESPONDENCIA

| Nivel | Nombre | Estado Documentado (v3.0) | Estado Implementado | Cobertura |
|---|---|---|---|---|
| **0** | PACKAGE | Biblioteca personal, `.lessons.cortex`, vivo | Inexistente como entidad aislada. Mezclado en Nivel 3. | 🔴 10% |
| **1** | BEHAVIORAL | Identidades, Roles, AXM/LIM, Elevación | Templates en `src/arqux/identities/`. Sin motor de elevación. | 🟡 40% |
| **2** | SKILL | `.md` procedimental, Nativas vs Heredadas | `src/arqux/skills/` existe. Falta soporte de `originals/`. | 🟢 70% |
| **3** | BRAIN | Estado vivo, 13 secciones, FCS/OBJ activos | `state.py` soporta 11 secciones. Sin validación de estado activo. | 🟡 50% |
| **--** | VALIDATORS | Módulo `src/arqux/validators/` con reglas E023-E034 | **DIRECTORIO INEXISTENTE** | 🔴 0% |

---

# 2. LISTA DE GAPS DETECTADOS

## GAP-01: Inexistencia de Capa de Validación (CRÍTICO)
- **Nivel:** Transversal
- **Evidencia:** El directorio `src/arqux/validators/` no existe en el repositorio.
- **Descripción:** La v3.0 define errores estrictos (`E023_LEVEL1_LIVE_STATE`, `E024_LEVEL3_MISSING_FOCUS`, `E025_INVALID_SURVIVE`). Ninguno de estos errores está implementado ni es lanzado por `state.py` o `formats.py`.
- **Impacto:** El framework permite mutar el estado del proyecto a configuraciones semánticamente inválidas sin lanzar excepciones de gobernanza.

## GAP-02: Motor de Inferencia de Niveles Ausente (ALTO)
- **Nivel:** Transversal
- **Evidencia:** No existe función `infer_level()` en `state.py`, `formats.py` o `constants.py`.
- **Descripción:** La v3.0 (§6) establece 4 reglas de precedencia para inferir el nivel de un archivo `.cortex` (atributo `kind`, filename, firma de sigilos, default). El código actual trata los archivos como texto plano o YAML genérico.
- **Impacto:** Imposibilidad de aplicar reglas de escritura/lectura específicas por nivel.

## GAP-03: Validación de Estado Activo en BRAIN (CRÍTICO)
- **Nivel:** Nivel 3 (BRAIN)
- **Evidencia:** `src/arqux/state.py` (función `read_brain()`).
- **Descripción:** La v3.0 dicta que un `brain.cortex` DEBE tener al menos un `FCS` y un `OBJ` con `status != "done"`. El parser actual extrae el texto de las secciones `FOCUS` y `OBJECTIVES` pero no inspecciona los atributos de los sigilos `FCS` y `OBJ` para validar su estado.
- **Impacto:** Un proyecto puede operar sin foco ni objetivos, violando la regla fundamental de Nivel 3.

## GAP-04: Estructura Canónica del Brain Incompleta (ALTO)
- **Nivel:** Nivel 3 (BRAIN)
- **Evidencia:** `src/arqux/constants.py` y `src/arqux/state.py`.
- **Descripción:** La v3.0 define 13 secciones ($0 a $12). `constants.py` omite `IDENTITY`, `KNOWLEDGE`, `ISSUES`. `state.py` soporta `IDENTITY` y `KNOWLEDGE` en el mapeo, pero ignora por completo `$12: ISSUES`.
- **Impacto:** Handlers MCP no pueden leer ni escribir incidencias de manera estandarizada.

## GAP-05: Flujo de Nivel 0 (PACKAGE) y `.lessons.cortex` (MEDIO)
- **Nivel:** Nivel 0 (PACKAGE)
- **Evidencia:** `src/arqux/handlers/` y `src/arqux/learning.py`.
- **Descripción:** La v3.0 define `.lessons.cortex` como un archivo Nivel 0 donde se acumulan patrones antes de ser elevados a Nivel 1. La implementación actual inyecta las lecciones directamente en la sección `LESSONS` del `brain.cortex` (Nivel 3).
- **Impacto:** Contaminación del estado del proyecto (Nivel 3) con ruido de aprendizaje rutinario que aún no ha sido validado.

## GAP-06: Soporte de Skills Heredadas (BAJO)
- **Nivel:** Nivel 2 (SKILL)
- **Evidencia:** `src/arqux/skills/` y `src/arqux/handlers/skill.py`.
- **Descripción:** La v3.0 requiere el directorio `skills/originals/` para preservar MDs de terceros y un flag `kind:"inherited"`. Ninguno existe en la implementación actual.
- **Impacto:** Trazabilidad perdida al adoptar skills de la industria.

## GAP-07: Persistencia de Identidades de Usuario (MEDIO)
- **Nivel:** Nivel 1 (BEHAVIORAL)
- **Evidencia:** Estructura del workspace `.arqux/`.
- **Descripción:** Las identidades nativas residen en `src/arqux/identities/`. Sin embargo, el workspace de usuario (`.arqux/`) no contiene un directorio `identities/`, solo `agents.cortex`. No está claro si las identidades creadas por el gobernador se persisten como archivos `.cortex` independientes o como entradas dentro de `agents.cortex`.
- **Impacto:** Ambigüedad en el ciclo de vida de identidades personalizadas.

---

# 3. PRIORIZACIÓN POR IMPACTO

1. **CRÍTICO (Bloqueante):** GAP-01 (Validadores), GAP-03 (Estado Activo Brain). Sin esto, la gobernanza es una ilusión.
2. **ALTO (Arquitectónico):** GAP-02 (Inferencia), GAP-04 (Secciones Brain). Rompe la integración MCP y el estado compartido.
3. **MEDIO (Operacional):** GAP-05 (Nivel 0), GAP-07 (Identidades). Afecta la limpieza del aprendizaje y la gestión de agentes.
4. **BAJO (Extensibilidad):** GAP-06 (Skills Heredadas). Funcionalidad futura.

---

# 4. ROADMAP DE CORRECCIÓN RECOMENDADO

## Fase 1: Cimientos de Gobernanza (Inmediato)
1. **Crear `src/arqux/validators/`**: Implementar `level_validator.py` con las reglas E023, E024, E025, E034.
2. **Implementar `infer_level()`**: En `formats.py`, aplicar las 4 reglas de precedencia de la v3.0.
3. **Integrar Validación en Write-Path**: Modificar `state.py` y `handlers/cortex.py` para que todo `write_cortex_pair()` pase por el validador de nivel correspondiente antes de persistir.

## Fase 2: Adecuación de Nivel 3 (BRAIN)
1. **Completar Constantes**: Añadir `BRAIN_SECTION_IDENTITY`, `BRAIN_SECTION_KNOWLEDGE`, `BRAIN_SECTION_ISSUES` a `constants.py`.
2. **Parser de Estado Activo**: Implementar lógica en `read_brain()` que parsee los sigilos `FCS` y `OBJ` y lance `E024` si no hay al menos uno con `status` "current" o "blocked".
3. **Soporte ISSUES**: Añadir mapeo para la sección `$12` en `state.py`.

## Fase 3: Separación de Nivel 0 y Nivel 1
1. **Aislar `.lessons.cortex`**: Modificar `learning.py` para que el aprendizaje rutinario escriba en `.arqux/lessons.cortex` (Nivel 0) en lugar del `brain.cortex`.
2. **Motor de Elevación**: Crear handler `cortex.elevate()` que mueva sigilos desde Nivel 0 a Nivel 1 tras validación.
3. **Clarificar Identidades**: Definir si `.arqux/identities/` debe crearse en `workspace.init()` para albergar identidades clonadas/personalizadas.

## Fase 4: Extensibilidad de Nivel 2
1. **Crear `src/arqux/skills/originals/`**: Estandarizar el flujo de ingesta de skills de terceros.

---

$11: CONCURRENCY
ERR:brain{version:"1", last_writer:"jarvis", updated:"2026-07-10T16:00:00Z"}