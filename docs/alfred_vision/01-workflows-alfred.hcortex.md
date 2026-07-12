# 01-workflows-alfred.hcortex.md
> Mapeo de mecanismos: de la solicitud del Arquitecto a la accion del agente
> Proyecto: ARQUX
> Generado: 2026-07-12
> Idioma: español
> Autor: Alfred

---

$0: METADATA
IDN:alfred_map{ name:"Mapa de Mecanismos Alfred", version:"4", purpose:"Mapear cada posible solicitud del Arquitecto al mecanismo que la resuelve: workflow, handler nativo, o conversacion BLP. Con aprobacion obligatoria y PULSE por destinatario.", categorias:["CONTEXTUAL","CONDUCTUAL","OPERACIONAL"], triage:"accion acotada con intencion clara?", movimientos:4 }
WRK:alfred_map{ status:"borrador", basa_en:"00-MANIFIESTO.hcortex.md v7 + 02-arquitectura-nativa.hcortex.md v4" }

---

$1: MAPEO COMPLETO

| Categoria | Solicitud del Arquitecto | Mecanismo | Handlers | Aprobacion |
|---|---|---|---|---|---|
| **CX** | "Trabajemos aqui" / "Inicia sesion" | w03 session | context.full + cortex.read | Arquitecto confirma contexto |
| **CX** | "Cambiemos al proyecto X" | w02 project | cortex.read(brain.cortex) + project.switch | Arquitecto confirma cambio |
| **CX** | "Abre un ciclo nuevo para [X]" | cycle.create directo | cycle.create | Arquitecto confirma nuevo ciclo |
| **CC** | "Registra esta leccion: ..." | handler directo | identity.record | Arquitecto confirma leccion |
| **CC** | "Necesito adoptar un agente nuevo" | w06 adoption + w05 | protocol.adopt + identity.record | Arquitecto confirma adopcion |
| **CC** | "Traspasa contexto a Agente X" | w10 handoff | session.close + handoff handlers | Arquitecto confirma traspaso |
| **OP** | "Arregla este bug en [archivo]" | w04 task | task.create → review → ejecutar → complete | **Obligatoria.** task.create + "¿Apruebas?" + PULSE review approved |
| **OP** | "Disenemos un modulo de [X]" | w08 BLP conversacional | context.full → conversacion → synthesize → render → approve | **Obligatoria.** blueprint presentado + "¿Apruebas?" |
| **OP** | "Importa este skill nuevo" | w07 + handler directo | skill.import + skill.edit | Arquitecto confirma importacion |
| **OP** | "Agrega una entrada a brain.cortex" | handler directo | cortex.entry.add | No requiere (el contenido lo dicta el Arquitecto) |
| **OP** | "Repara este archivo .cortex" | w11 repair | cortex.verify + cortex.repair | Arquitecto confirma reparacion |

$2: EL TRIAGE — UNA SOLA PREGUNTA

Cuando el Arquitecto habla, w00 hace 1 pregunta:

```
¿Es una acción acotada con intención clara?
  ├──→ SÍ → TAREA DIRECTA (aunque el resultado sea incierto)
  │     "Diagnostica el servidor" = tarea. AC claros: CPU, RAM,
  │     disk, red. El resultado concreto es incierto, pero la
  │     intención y los límites están definidos.
  │     → 3 movimientos: task.create + ejecutar + complete
  │
  └──→ NO → DISEÑO (BLP)
        "Necesito un sistema de auth" = diseño. Los requisitos
        no están definidos. Necesitamos conversación primero.
        → BLP conversacional → blueprint → tareas derivadas
```

Luego de determinar si es tarea o diseño, se clasifica en la
categoria correspondiente:

| Categoria | ¿La solicitud... | Mecanismo | Aprobacion |
|---|---|---|---|---|
| **CX** | cambia dónde estamos? | handlers nativos: cortex.read(brain.cortex), cycle.current, context.detect | No requiere task.create. El Agente propone el cambio, Arquitecto confirma. |
| **CC** | cambia quién soy o cómo actúo? | handler directo: identity.record | No requiere task.create. El Agente presenta la lección, Arquitecto confirma. |
| **OP** | es trabajo operacional? | 4 movimientos: Marco → Revisar → Ejecutar → Cerrar | **Obligatoria.** task.create + presentar + "¿Apruebas?" + approved en PULSE |

$2.1: Ejemplos de clasificacion

| Solicitud | ¿Acción acotada? | Categoria | Mecanismo | Aprobacion |
|---|---|---|---|---|
| "Arregla el login" | **Sí** — intención clara | OP | task.create → presentar → ejec. → complete | "Propongo arreglar login. ¿Apruebas?" |
| "Diagnostica el servidor" | **Sí** — AC claros (CPU, RAM, disk) | OP | task.create → presentar → ejec. → complete | "Propongo diagnostico con AC X,Y,Z. ¿Apruebas?" |
| "Necesito un sistema de auth" | **No** — requisitos a definir | OP (BLP) | conversación → synthesize → presentar → approve | "Este es el blueprint. ¿Apruebas?" |
| "Vamos al proyecto ARQUX-beta" | **Sí** — cambiar proyecto es acotado | CX | cortex.read(brain.cortex) + handler de cambio | "Cambio a proyecto ARQUX-beta. ¿Confirmas?" |
| "Aprende de este error: ..." | **Sí** — la lección está definida | CC | identity.record directo | "Registro: [lección]. ¿Confirmas?" |
| "Que proyectos tengo?" | **Sí** — es una consulta acotada | — | handlers de lectura | No requiere (solo lectura) |

$3: NO TODO ES WORKFLOW

Cuando usar workflow vs handler directo:

| Usar workflow cuando... | Usar handler directo cuando... |
|---|---|
| Hay incertidumbre en la solucion | La solucion es conocida y exacta |
| Se requieren multiples pasos secuenciales | Es una operacion atomica |
| Se necesita revision externa (stakeholders) | El Arquitecto confia en la ejecucion |
| El resultado es un artefacto nuevo | Es una modificacion local |
| No se sabe exactamente que handlers invocar | Se sabe exactamente que handler usar |

**Ejemplos de handlers directos** (sin workflow):
- `identity.record` — "registra que aprendi X"
- `cortex.entry.add` — "agrega esta entrada al brain"
- `skill.edit` — "actualiza la seccion Y del skill Z"
- `evidence.record` — "deja constancia de X"
- `project.status` — "muestrame el estado del proyecto"

$4: TRIAGE PARA MODELOS DEBILES (NANO)

Para agentes NANO (<8K), el triage se simplifica:

```
¿Es una acción acotada con intención clara?
  ├──→ SÍ → "Propongo: [obj] con AC: [ac]. ¿Apruebas?"
  │         → task.create + presentar + [si approve] ejecutar + complete
  └──→ NO → "Arquitecto, necesito mas contexto para saber qué hacer.
             ¿Prefieres que diseñemos juntos una solución?"
```

Sin w00 formal. Sin 3 categorías. Sin CX/CC/OP.
Solo: proponer, esperar aprobacion, ejecutar, cerrar.
El prompt del agente NANO ya contiene esta lógica.

$5: RESUMEN GRAFICO

```
                         w00 TRIAGE
                     ┌─────────┴──────────┐
                     │  3 preguntas en     │
                     │  orden: CX→CC→OP   │
                     └──┬──┬──┬───────────┘
                        │  │  │
              ┌─────────┘  │  └──────────────┐
              ▼            ▼                 ▼
      ┌───────────┐ ┌───────────┐ ┌───────────────┐
      │CONTEXTUAL │ │CONDUCTUAL │ │  OPERACIONAL   │
      │ (CX)      │ │ (CC)      │ │   (OP)         │
      ├───────────┤ ├───────────┤ ├───────────────┤
      │w01 w02    │ │w05 w06    │ │w04 w07 w08    │
      │w03        │ │w10        │ │w09 w11        │
      │cycle.create│ │identity.  │ │+ handlers     │
      │           │ │record     │ │directos        │
      └───────────┘ └───────────┘ └───────────────┘
```

---

$11: REVISION

ERR:alfred_map{ version:"4", generated:"2026-07-12", author:"Alfred", categorias:3, triage:"accion acotada con intencion clara? → proponer → aprobar → ejecutar", movimientos:4, workflows_referenciados:["w01","w02","w03","w04","w05","w06","w07","w08","w09","w10","w11"], handlers_nativos:["identity.record","cortex.entry.add","skill.edit","cortex.read","cycle.current","context.detect","identity.get"] }
