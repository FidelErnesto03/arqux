# 02-arquitectura-nativa.hcortex.md
> Diseño de interacción nativa: cómo fluye la coreografía del gobierno en ArqUX
> Proyecto: ARQUX
> Generado: 2026-07-12
> Idioma: español
> Autor: Alfred

---

$0: METADATA
IDN:nativa{ name:"Arquitectura Nativa ArqUX", version:"2", purpose:"Definir como la interaccion agente-Arquitecto ocurre de forma nativa: CORTEX como lingua franca, 3 movimientos como patron universal, handlers con canal I/E/B, PULSE en brain.cortex, sin filesystem.", basa_en:"00-MANIFIESTO.hcortex.md v5 + 01-workflows-alfred.hcortex.md v1 + correcciones del Arquitecto" }
WRK:nativa{ status:"diseno", autor:"Alfred", piezas:["w00 entry","3 movimientos","handlers I/E/B","brain.cortex $PULSE","handlers nativos","tiers"] }

---

$1: ANATOMIA DE UNA INTERACCION NATIVA

Todo empieza igual:

```
Arquitecto: [lenguaje natural]

┌── w00 ─────────────────────────────────────────────────┐
│ 1 pregunta: "¿Acción acotada con intención clara?"     │
│   ├── SÍ → TAREA: aunque el resultado sea incierto    │
│   └── NO → DISEÑO: necesitamos definir requisitos     │
└────────────────────────────────────────────────────────┘

       │
       ▼

┌── 4 MOVIMIENTOS ──────────────────────────────────────┐
│ Marco:   task.create(obj, ac)                          │
│ Revisar: presentar al Arquitecto + obtener aprobacion  │
│ Ejecutar: [trabajo real con handlers nativos]          │
│ Cierre:  task.complete(id, evidence)                   │
│           + brain.cortex $PULSE en cada movimiento     │
└────────────────────────────────────────────────────────┘

       │
       ▼

Alfred: [respuesta en lenguaje natural + evidencia]
```

**La interacción nativa es asincrónica:**
- El Arquitecto habla natural
- El agente ejecuta a través de handlers nativos (no filesystem)
- El agente registra en brain.cortex $PULSE
- El agente responde natural

El formato CORTEX es el lenguaje de la máquina. Los handlers son
la interfaz nativa. El lenguaje natural es el puente con el humano.
w00 es el traductor entre ambos mundos.

$2: LOS 4 MOVIMIENTOS — PATRON UNIVERSAL

No importa si es CX, CC u OP. No importa si el agente es FULL o NANO.
Toda operación sigue 4 movimientos:

```
MOVIMIENTO 1: MARCO
  handler: task.create
  entrada: obj + acceptance_criteria
  salida:  task_id
  registro: brain.cortex $PULSE { from:alfred to:alfred, E-NNN, create, task_id, obj, ts }
  propiedad: idempotente (mismo obj + mismo contexto → misma tarea)

MOVIMIENTO 2: REVISAR
  handler: [conversacional — el agente presenta la propuesta]
  entrada: task_id + propuesta al Arquitecto
  salida:  approved | rejected
  registro: brain.cortex $PULSE { from:arquitecto to:alfred, E-NNN, review, task_id, status, ts }
  propiedad: Sin approved, no hay movimiento 3. Es el corazon del gobierno.

MOVIMIENTO 3: EJECUCION
  handler: [el que corresponda nativamente]
  entrada: depende del trabajo
  salida:  resultado del trabajo
  registro: brain.cortex $PULSE { from:alfred to:alfred, E-NNN, progress, task_id, detalle, ts }
  propiedad: checkpointeable (se retoma si falla)

MOVIMIENTO 4: CIERRE
  handler: task.complete
  entrada: task_id + evidence
  salida:  confirmacion
  registro: brain.cortex $PULSE { from:alfred to:alfred, E-NNN, complete, task_id, evidence, ts }
  propiedad: idempotente (complete 2 veces = mismo estado)
```

**Excepciones al patron:**
- **Lecturas (consulta):** Solo movimiento 3 (ejecutar la consulta).
  No hay marco, revision ni cierre porque no se muta estado.
- **CX puro (cambio de proyecto):** Movimientos 1 + 2 + 4.
  Marco: task.create. Revision: "cambio a proyecto X, ¿apruebas?".
  Cierre: task.complete. No hay "ejecucion" porque el handler de
  cambio de proyecto es la accion misma.
- **BLP conversacional:** Los 4 movimientos ocurren al final, cuando
  se crean las tareas derivadas del blueprint aprobado. La conversacion
  de diseno previa no requiere task.create — es exploracion, no ejecucion.

$3: HANDLERS NATIVOS — SIN FILESYSTEM

El agente **no escanea el filesystem**. Todo lo que necesita lo
obtiene a través de handlers que exponen la información directamente:

| Necesidad | Handler nativo | En lugar de escanear... |
|---|---|---|---|
| Detectar .arqux/ | `context.detect()` | Buscar directorio hacia arriba |
| Identidad de un agente | `identity.get("alfred")` | Leer identities/alfred.cortex |
| Proyecto activo | `cortex.read("brain.cortex $2")` | Leer brain.cortex con selector |
| Ciclo activo | `cycle.current()` | Leer cycles/ directorio |
| Identidad específica | `identity.get("jarvis")` | Leer identities/ directorio |
| Leer brain.cortex | `cortex.read(selector)` | Open + parse manual |
| Escribir en brain.cortex | `cortex.entry.add()` | Edit manual del archivo |

**Principio:** Los handlers son la interfaz nativa entre el agente
y el sistema. El agente no sabe ni le importa si el backend usa
archivos, base de datos, o una API remota.

Esto garantiza:
- **Independencia de implementacion:** El backend cambia, los
  handlers no. El agente no se entera.
- **Modelos debiles:** Solo necesitan recordar nombres de handlers,
  no estructuras de directorios.
- **Control de acceso:** El handler puede validar, loggear, auditar.

$4: HANDLERS CON CANAL I/E/B

Los handlers no reciben parametros planos — reciben **contenido CORTEX**.

```
CANAL I (Input):  El handler acepta un bloque CORTEX como entrada.
CANAL E (Output): El handler devuelve un bloque CORTEX como salida.
CANAL B (Batch):  El handler procesa multiples entradas en 1 llamada.
```

$4.1: Ejemplo — task.create con canal I

```
Hoy (parametros planos, no nativo):
  task.create(obj="arreglar login", ac=["test passes"], priority="high")

Nativo (canal I):
  task.create(content="""
    OBJ: arreglar login
    AC:
      - los tests pasan
      - el flujo de error se mantiene
    PRIORIDAD: alta
  """)
```

$4.2: Ejemplo — cortex.entry.add con canal I

```
Hoy (parametros planos, no nativo):
  cortex.entry.add(path="brain.cortex", section="$5", sigil="LNG",
    name="leccion_login", value="siempre validar input")

Nativo (canal I):
  cortex.entry.add(content="""
    PATH: brain.cortex
    SECTION: $5
    LNG:leccion_login{ value:"siempre validar input" }
  """)
```

$4.3: Ventaja del canal I

- **Modelos debiles no necesitan recordar la firma del handler.**
  Escriben CORTEX en lenguaje natural y el handler lo parsea.
- **El formato es el mismo para todos los handlers.** Una vez que
  el agente sabe escribir CORTEX, sabe usar cualquier handler.
- **Autodocumentado.** El contenido CORTEX es autoexplicativo.
  No requiere consultar documentacion externa.

$4.4: El canal I y la aprobacion

El handler task.create con canal I produce una propuesta que el
Arquitecto revisa:

```
task.create(content="""
  OBJ: diagnosticar servidor de produccion
  AC:
    - reporte de CPU, RAM, disco, red
    - estado de servicios criticos
    - alertas activas
  PRIORIDAD: alta
""")

→ brain.cortex $PULSE: from:alfred   to:alfred     E-001 create T-042

Agente: "Propongo diagnosticar el servidor de producción.
         AC: reporte de CPU/RAM/disco/red, estado de servicios,
         alertas activas. ¿Apruebas la tarea?"

Arquitecto: "Apruebo"

→ brain.cortex $PULSE: from:arquitecto to:alfred     E-002 review T-042 approved

[Ejecutar el diagnostico...]

→ brain.cortex $PULSE: from:alfred   to:alfred     E-003 progress T-042 ...
→ brain.cortex $PULSE: from:alfred   to:alfred     E-004 complete T-042 evidence
```

$5: BRAIN.CORTEX — UN SOLO ARCHIVO, UNA SOLA FUENTE DE VERDAD

No hay pulse.jsonl separado. No hay identities/ directorio escaneable.
Todo vive en brain.cortex o se accede via handlers:

```
brain.cortex
├── $1: FCS            ← Modo actual, configuracion
├── $2: WRK            ← Tarea activa, BLP activo
├── $3: OBJ            ← Objetivos del proyecto
├── $4: RSK            ← Riesgos detectados
├── $5: LNG            ← Lecciones aprendidas
├── $6: KNW            ← Conocimiento acumulado
├── $7: PULSE          ← Latido del sistema por destinatario (append-only)
│     from:alfred to:alfred
│     E-001: create T-042 "arreglar login"
│     E-002: review T-042 approved
│     E-003: progress T-042 "edit login.py:17"
│     E-004: complete T-042 "login.py:17-23 fix"
│
└── $8: ...            ← Futuro
```

$5.1: PULSE con ámbito por destinatario

El pulso no es global. Cada entrada lleva `from` (quién emite) y `to`
(quién recibe). La visibilidad se determina por destinatario:

```
from:alfred to:alfred     → Entra en la rotación de Alfred
from:jarvis to:alfred     → Entra en la rotación de Alfred (destinatario)
from:alfred to:jarvis     → NO entra en rotación de Alfred. Solo en Jarvis.
```

**Cada agente lee §7 filtrado por su identidad.** Cuando Alfred lee
brain.cortex §7, solo ve los pulsos donde `to = alfred` o `from = alfred`.
Los pulsos ajenos (ej: `from:jarvis to:system`) no existen para él.

$5.2: Rotación del PULSE

§7 almacena los últimos N pulsos del agente (ej: 100). Cuando excede,
los más viejos se archivan a §7-archive. brain.cortex mantiene un
tamaño manejable.

```
§7 (activo, 100 entradas max)
  → al exceder, las más viejas pasan a §7-archive
  → el agente siempre lee §7 primero
  → si necesita histórico, lee §7-archive
```

$5.3: PULSE como latido

Cada movimiento del agente registra un pulso. La secuencia completa
de una tarea exitosa:

```
brain.cortex $PULSE (ámbito: alfred):
  E-001 | create   | T-042 "arreglar login"           | 12:00 | alfred→alfred
  E-002 | review   | T-042 approved                    | 12:01 | arquitecto→alfred
  E-003 | progress | T-042 "edit login.py:17"         | 12:02 | alfred→alfred
  E-004 | progress | T-042 "test: 3/3 pass"          | 12:04 | alfred→alfred
  E-005 | complete | T-042 "login.py:17-23 fix"       | 12:05 | alfred→alfred
```

**Nota:** Sin `review approved` no hay ejecución. Es el corazón
del gobierno.

**Propiedades:**
- **Inmutable:** Append-only. No se edita ni borra.
- **Secuencial:** El orden de los eventos es el orden de la historia.
- **Ámbito por destinatario:** Cada agente ve solo lo relevante.
- **Rotado:** §7 mantiene tamaño constante. Histórico en §7-archive.

$5.4: Checkpoint natural

Si un agente falla, el siguiente agente lee brain.cortex §7 filtrado
por su identidad y sabe exactamente en qué punto quedó:

```
brain.cortex $PULSE (ámbito: alfred):
  E-001: create T-042 OK
  E-002: review T-042 approved OK
  E-003: progress "edit login.py:17" OK
  ¿complete? NO → T-042 esta pendiente de cierre
```

Retoma sin preguntar al Arquitecto. Sin escanear filesystem.

Si el PULSE muestra `review rejected`, la tarea fue rechazada y
no debe continuar ni re-preguntar.

$5.3: brain.cortex en el triage

w00 revisa brain.cortex $2 (WRK) antes de clasificar:

```
brain.cortex $2/WRK:
  ├── ¿Tiene un BLP activo?
  │     → Continuar el BLP (diseño en progreso)
  ├── ¿Tiene una tarea en progreso?
  │     → Continuar la tarea (ejecucion en progreso)
  └── ¿Vacio?
        → Clasificar la nueva solicitud del Arquitecto
```

$6: TRIAGE NATIVO (w00)

El triage no es un handler MCP. Es un **patrón conversacional**
que el agente ejecuta al recibir cualquier input:

```
Input del Arquitecto
  │
  ▼
┌──────────────────────────────────────────────────┐
│ Paso 1: Revisar brain.cortex $2 (WRK)            │
│   ├── ¿Hay tarea o BLP en progreso?              │
│   │     → Continuar lo que estaba haciendo       │
│   └── ¿Vacio?                                    │
│         → Siguiente paso                         │
└──────────────────────┬───────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────┐
│ Paso 2: "¿Acción acotada con intención clara?"    │
│                                                    │
│   SÍ → TAREA DIRECTA                               │
│     "Diagnostica el servidor" → AC claros           │
│     "Arregla el login" → intención clara           │
│     → MARCO: task.create                           │
│     → REVISAR: presentar propuesta + "¿Apruebas?" │
│     → EJECUTAR: handlers nativos                   │
│     → CERRAR: task.complete + evidence             │
│                                                    │
│   NO → DISEÑO (BLP)                                │
│     "Necesito un sistema de auth"                   │
│     "Crea un modulo de reporting"                   │
│     → Conversación de diseño                       │
│     → blueprint.synthesize                         │
│     → PRESENTAR blueprint + "¿Apruebas?"           │
│     → [si aprobado] tareas derivadas               │
└──────────────────────┬───────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────┐
│ Paso 3: Una vez aprobado, EJECUTAR                │
│   ├── CX: handlers de contexto                    │
│   ├── CC: handler identity.record                 │
│   └── OP: ejecutar con handlers nativos           │
│                                                    │
│   Nota: Sin "approved" en brain.cortex $PULSE,     │
│   NO hay ejecución. El agente no pasa del paso 2. │
└──────────────────────────────────────────────────┘
```

$7: TIERS NATIVOS

| Aspecto | NANO | LITE | FULL |
|---|---|---|---|---|
| brain.cortex | Solo escribe complete | Lee al inicio, escribe create+complete | Lee y escribe todo |
| PULSE | Solo complete | create + review + complete | create + review + progress + complete |
| w00 | No existe (2 preguntas fijas en prompt) | Pregunta "acción acotada?" + espera aprobacion | Clasifica, propone, espera aprobacion |
| Handlers | task.create, task.complete, identity.record | w00-w08 + task.claim + handlers nativos | w00-w11 + task.claim + handlers nativos |
| Movimientos | task.create → presentar → ejec. → complete (sin claim) | 4 movimientos con claim para asignación divergente | 4 movimientos con claim para multi-agente |
| CX | No maneja | Via handlers nativos, resumido | Via handlers nativos, completo |
| Recuperacion | No tiene | Lee brain.cortex §PULSE filtrado por to:self | Checkpoints activos en §WRK + §PULSE |

$8: MAPA DE ARQUITECTURA — VISTA NATIVA

```
Arquitecto (lenguaje natural)
     │
     ▼
┌──────────┐
│   w00    │  Triage: 1 pregunta
│  triage  │  ¿Acción acotada?
└────┬─────┘
     │
      ├── CX ───→ handlers: cortex.read(brain.cortex), cycle.current, context.detect
     │           registro: brain.cortex $PULSE
     │
     ├── CC ───→ handler:  identity.record
     │           registro: brain.cortex $LNG + $PULSE
     │
     └── OP ───→ 3 movimientos:
                  Marco:    task.create → brain.cortex $PULSE
                  Ejecutar: handlers nativos → brain.cortex $PULSE
                  Cierre:   task.complete → brain.cortex $PULSE + $WRK
```

**El agente solo toca 2 cosas:**
1. **Handlers nativos** para toda operación
2. **brain.cortex** para memoria y pulso

No escanea directorios. No parsea archivos sueltos. No mantiene
estado local. Todo fluye a través de handlers → brain.cortex.

$9: REGLAS DE INTERACCION NATIVA

1. **El Arquitecto habla en lenguaje natural. Siempre.**
2. **w00 clasifica por naturaleza de la solicitud:**
   ¿acción acotada con intención clara? → Tarea.
   ¿Necesitamos definir requisitos? → BLP.
3. **Toda operación sigue 4 movimientos:** Marco → Revisar → Ejecutar → Cierre.
4. **Sin aprobación previa del Arquitecto, no hay ejecución.**
   El agente propone, el Arquitecto dispone. El PULSE `review approved`
   es requisito obligatorio antes del movimiento 3.
5. **task.create y task.complete son obligatorios** en OP.
6. **Sin filesystem.** El agente no escanea directorios.
   Los handlers son su interfaz nativa al sistema.
7. **Un solo archivo de estado: brain.cortex.** PULSE vive en §7.
   No hay pulse.jsonl separado.
8. **PULSE tiene ámbito por destinatario.** Cada entrada lleva `from` y `to`.
   El agente solo ve pulsos donde `to = self` o `from = self`.
9. **PULSE tiene rotación.** §7 mantiene max 100 entradas recientes.
   Las más viejas pasan a §7-archive. El agente siempre lee §7 primero.
10. **task.claim se mantiene para asignación divergente.** Cuando el agente
    que ejecuta es distinto del que creó la tarea, claim documenta la
    asignación. Para el caso común (mismo agente), claim es implícito.
11. **Handlers con canal I** aceptan CORTEX nativo como entrada.
12. **Modelos debiles (NANO)** usan el mismo patrón con menos handlers
    y sin triage formal — el prompt hace las veces de w00.

---

$11: REVISION

ERR:nativa{ version:"4", generated:"2026-07-12", author:"Alfred", basa_en:"00-MANIFIESTO v7 + resoluciones del Arquitecto", cambios_v4:["PULSE con from/to","rotacion §7→§7-archive","task.claim mantenido para multi-agente"], movimientos:4, categorias:3, tiers:3 }
