---
# Plantilla de Manifiesto de Ciclo (CYCLE_MANIFEST_TEMPLATE.md)
# Copiada por cycle.create() para crear CYCLE-NNN/MANIFEST.md
# Formato HCORTEX — legible por humanos y máquinas

cycle_id: ""
name: ""
project_ref: ""
status: "draft"
governor: ""
created_at: ""
updated_at: ""
closed_at: ""
planned_start: ""
planned_end: ""
quality_gates@: {
  has_clear_purpose: false,
  has_explicit_scope: false,
  has_measurable_objectives: false,
  has_operational_guidelines: false,
  has_control_points: false,
  aligns_with_project: false,
}
_template_ref: "CYCLE_MANIFEST_TEMPLATE.md"
---

# Manifiesto: {name}

> Documento rector del ciclo. Define identidad, alcance, objetivos, directrices y puntos de control. Fuente de verdad para todos los Blueprints dentro de este ciclo.

---

## §1: Propósito

<!-- CYCLE:1 -->
_¿Por qué existe este ciclo? ¿Qué problema aborda dentro del proyecto?_

**Relación con los objetivos del proyecto:**
_¿A qué objetivos del proyecto (desde brain.cortex OBJ) contribuye este ciclo?_
<!-- /CYCLE:1 -->


## §2: Alcance y Límites

<!-- CYCLE:2 -->
**Dentro del alcance de este ciclo:**
- _Ítem 1_
- _Ítem 2_

**Fuera del alcance (excluido explícitamente):**
- _Ítem 1_
- _Ítem 2_

> Lo que está fuera del alcance NO debe ser abordado por ningún Blueprint de este ciclo.
<!-- /CYCLE:2 -->


## §3: Objetivos

<!-- CYCLE:3 -->
_Objetivos concretos y medibles del ciclo. Cada Blueprint debe contribuir al menos a uno._

- [ ] **CYC-OBJ-1:** _Objetivo — criterio de éxito_
- [ ] **CYC-OBJ-2:** _Objetivo — criterio de éxito_
- [ ] **CYC-OBJ-3:** _Objetivo — criterio de éxito_
<!-- /CYCLE:3 -->


## §4: Directrices

<!-- CYCLE:4 -->
_Directrices operacionales que rigen todos los Blueprints de este ciclo._

1. _Directriz 1 — ej., "Los Blueprints de infraestructura tienen prioridad sobre los de funcionalidad"_
2. _Directriz 2 — ej., "Todo Blueprint debe incluir un diagrama PUML en la sección de diseño"_
3. _Directriz 3 — ej., "Ningún Blueprint se cierra sin ejecutar todas las validaciones requeridas"_
4. _Directriz 4 — ej., "Las dependencias entre Blueprints deben resolverse antes de que el dependiente comience"_

**Directrices para creación de Blueprints:**
1. _Cada Blueprint debe referenciar el objetivo del ciclo al que contribuye_
2. _Los Blueprints críticos deben incluir un plan de reversión_
3. _Cada Blueprint debe estimar su impacto en los criterios de éxito del ciclo_
<!-- /CYCLE:4 -->


## §5: Puntos de Control

<!-- CYCLE:5 -->
_Hitos, revisiones y puntos de validación. La ejecución se detiene en cada punto._

| ID | Tipo | Fecha Planificada | Descripción | Criterio de Aprobación |
|---|---|---|---|---|
| CP-01 | Revisión de Diseño | _YYYY-MM-DD_ | _Descripción_ | _¿Qué debe cumplirse?_ |
| CP-02 | Control Intermedio | _YYYY-MM-DD_ | _Descripción_ | _¿Qué debe cumplirse?_ |
| CP-03 | Revisión Final | _YYYY-MM-DD_ | _Descripción_ | _¿Qué debe validarse?_ |

> Los puntos de control son obligatorios. El gobernador debe informar al Arquitecto al aproximarse a uno.
<!-- /CYCLE:5 -->


## §6: Blueprints (Índice)

<!-- CYCLE:6 -->
_Índice breve de los Blueprints asignados a este ciclo. Se auto-pobla._

| BLP ID | Título | Estado | Prioridad | Objetivo | Gobernador |
|---|---|---|---|---|---|
| _BLP-NNN_ | _Título_ | _draft/ready/..._ | _critical/high/medium/low_ | _CYC-OBJ-N_ | _agente_ |
<!-- /CYCLE:6 -->


## §7: Estado y Métricas

<!-- CYCLE:7 -->
**Estado actual:** draft
**Total Blueprints:** 0 | **Draft:** 0 | **Madurando:** 0 | **Ready:** 0 | **En Progreso:** 0 | **Done:** 0
**Progreso:** 0%
**Próximo punto de control:** _CP-NN — Fecha_
**Iniciado:** _YYYY-MM-DD_ | **Fin planificado:** _YYYY-MM-DD_
<!-- /CYCLE:7 -->


## §8: Reglas del Ciclo

<!-- CYCLE:8 -->
_Reglas específicas de este ciclo._

1. _Regla 1_
2. _Regla 2_
<!-- /CYCLE:8 -->


## §9: Contrato de Calidad

<!-- CYCLE:9 -->
| Compuerta | Estado |
|---|---|
| has_clear_purpose | ☐ |
| has_explicit_scope | ☐ |
| has_measurable_objectives | ☐ |
| has_operational_guidelines | ☐ |
| has_control_points | ☐ |
| aligns_with_project | ☐ |

> Todas las compuertas deben estar en ✅ antes de cycle.ready(). Ver blueprint-workflow skill, §4.1.
<!-- /CYCLE:9 -->
