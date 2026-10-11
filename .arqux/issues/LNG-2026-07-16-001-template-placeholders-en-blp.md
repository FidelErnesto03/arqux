# ISSUE: Template placeholders no reemplazados ni declarados como N/A en BLPs

## IDN

| Campo | Valor |
|---|---|
| **ID** | LNG-2026-07-16-001 |
| **Fecha** | 2026-07-16 |
| **Severidad** | Media |
| **Estado** | verified (chequeo automático pre-ready VIGENTE: gate BLP-009/BUG-004 P3 en blueprint.ready bloquea con lista explícita de placeholders — _pending_placeholders template-driven, §18 excluido, sin falsos positivos de identificadores; verificado 2026-09-30 T-029 CYCLE-12, 28 tests de guards/ready en verde, PULSE E-0934/E-0935; la declaración N/A se expresa reemplazando el marcador con 'N/A', que satisface el gate) |
| **Detectado por** | Arquitecto (post-auditoría Heimdall) |
| **Proyecto** | ARQUX |
| **Ciclo** | CYCLE-07 |
| **Agente** | Heimdall |
| **BLP afectado** | BLP-012 (patrón replicable en BLP-013, BLP-014, BLP-015) |

## WRK — Working State

Durante la revisión de BLP-012, el Arquitecto detectó que varias secciones del BLP contenían **template placeholders literales** del BLP_TEMPLATE.md en vez de contenido real o una declaración explícita de "No aplica".

### Secciones afectadas en BLP-012

| Sección | Contenido actual | Lo que debería decir |
|---|---|---|
| §5 Contexto | `_Diagrama PUML que muestra el entorno... @startuml... @enduml_` | "No aplica — BLP de remediación documental, no de construcción de componentes" |
| §8 Diseño Técnico | `_Arquitectura esperada: componentes... @startuml... @enduml_` | "No aplica — no se crean componentes nuevos" |
| §9 Diseño Operacional | `_Diagrama de secuencia... @startuml... @enduml_` | "No aplica — la ejecución está definida en §11 Procedimiento de Trabajo" |
| §10 Contratos | `_Formato, archivo o payload de entrada_ / _Archivos creados..._` | "No aplica — no hay contratos de API nuevos" |
| §18 Contrato de Calidad | 7 gates en ☐ | Deben reflejar el estado real del BLP |

### Patrón detectado

1. Agente crea BLP con blueprint.create() → template se copia con placeholders
2. Agente escribe contenido en las secciones que considera "importantes" (§1, §2, §3, §12, §14)
3. Agente **omite las secciones tipo diseño/PUML** asumiendo tácitamente que "no aplican"
4. Agente DEJA los placeholders del template en lugar de reemplazarlos por "N/A" explícito
5. Arquitecto lee el BLP y encuentra secciones con instrucciones genéricas del template
6. Arquitecto no sabe si el agente se olvidó, está pendiente, o realmente no aplica

### Causa raíz

El agente **prioriza velocidad de poblamiento sobre completitud semántica**. En lugar de evaluar cada sección individualmente y decidir si aplica o no, el agente:

- Salta secciones que parecen "de diseño" (PUML, diagramas, contratos) asumiendo que no son necesarias
- No declara explícitamente "No aplica" porque requiere más tiempo que dejar el placeholder
- Asume que el ejecutor (o el Arquitecto) interpretará correctamente la omisión
- Confía en que la cantidad de secciones llenas compensa la calidad de cada sección

Esto es una variante del patrón documentado en LNG-2026-07-15-001 (BLPs presentados incompletos), pero a nivel intra-BLP en vez de inter-BLP.

## FCS — Focus

**Todo BLP debe tener 0 placeholders del template antes de pasar a ready.** Cada sección debe contener:
- Contenido real escrito por el agente, O
- "No aplica" explícito con una breve justificación de por qué no aplica

Los placeholders genéricos del template (`_Ítem 1_`, `_Descripción_`, `@startuml title Contexto — BLP-NNN`) son inaceptables en un BLP en estado draft presentado para revisión.

### Prevención

1. Antes de blueprint.ready(), ejecutar verificación automática: buscar placeholders del template en el BLP
   - Patrones a buscar: `_Ítem \d+_`, `_Descripción_`, `BLP-NNN`, `_comando_`, `@startuml title Contexto — BLP-NNN`
   - Si se encuentra algún match, el BLP no está listo para ready
2. Para secciones de diseño (PUML, diagramas, contratos) que no aplican, escribir explícitamente:
   `"No aplica — [razón breve de por qué esta sección no corresponde]"`
3. No asumir que el ejecutor o el Arquitecto interpretarán silenciosamente una sección omitida
4. El §18 Contrato de Calidad debe reflejar el estado real del BLP — no dejar todos los gates en ☐ como default

### Checklist de verración pre-ready

```
[ ] §1-§18 revisadas individualmente
[ ] 0 placeholders del template presentes
[ ] Cada sección con contenido real o "No aplica" explícito
[ ] §18 gates reflejan estado real
[ ] governor correcto para el proyecto
[ ] priority coherente con la severidad del BLP
```

## LNG — Lección

**Lección:** Template placeholder no es lo mismo que "No aplica". Si una sección del template no corresponde al tipo de BLP, debe decirse explícitamente con justificación. Un placeholder es una deuda técnica que el Arquitecto debe pagar interpretando.

**Prevención:** Escanear el BLP completo en busca de patrones del template antes de presentarlo. Cada sección debe tener contenido propio o un "No aplica" con razón. No hay secciones que "se saltan silenciosamente".
