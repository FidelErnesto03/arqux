# ArqUX 0.8

## Arquitectura de Gobierno para Actividades Humano-Agénticas

**Estado:** Propuesta de definición arquitectónica para v0.8
**Naturaleza:** Evolución mayor compatible conceptualmente con ArqUX v0.7
**Orientación:** Generalista, organizacional, operacional, extensible y agent-native

---

## 1. Definición

**ArqUX 0.8 es una arquitectura y runtime de gobierno para actividades ejecutadas conjuntamente por humanos, agentes de inteligencia artificial, automatizaciones, herramientas y sistemas externos.**

Su propósito es asegurar que cualquier actividad significativa pueda conservar una continuidad verificable entre:

**propósito → contexto → contrato → autoridad → decisión → ejecución → evidencia → aseguramiento → aceptación → conformidad → cierre → aprendizaje.**

Esta continuidad ya constituye uno de los fundamentos conceptuales de ArqUX.

La evolución 0.8 amplía ese principio para que ArqUX deje de asumir que el objeto gobernado es fundamentalmente un proyecto de software y pueda gobernar de forma natural actividades como:

| Dominio        | Ejemplos                                                              |
| -------------- | --------------------------------------------------------------------- |
| Ingeniería     | desarrollo, infraestructura, arquitectura, operaciones técnicas       |
| Compras        | búsqueda de proveedores, presupuestos, selección, adquisición         |
| Operaciones    | mantenimiento, logística, incidentes, inventario, procedimientos      |
| Administración | contratos, documentación, renovaciones, conciliaciones                |
| Comercial      | investigación de mercado, campañas, propuestas, seguimiento           |
| Finanzas       | presupuestos, análisis, conciliación, aprobación de gastos            |
| Investigación  | recopilación, análisis, comparación, informes, decisiones             |
| Legal          | revisión documental, control contractual, seguimiento de obligaciones |
| Calidad        | inspecciones, verificaciones, auditorías, acciones correctivas        |
| Gestión        | planificación, seguimiento, coordinación, evaluación y aprendizaje    |

Por tanto, ArqUX 0.8 no debe entenderse como un framework de agentes para desarrollo.

Debe entenderse como:

> **una infraestructura de gobierno para trabajo organizacional asistido y ejecutado por agentes.**

---

# 2. Cambio fundamental de alcance

ArqUX 0.7 parte correctamente de la noción de **Governed Activity** como objeto central, no del código fuente.

Sin embargo, la implementación 0.7.8 todavía conserva una importante herencia del desarrollo de software.

Su Blueprint predeterminado contiene Diseño Técnico, comandos, archivos creados o modificados, tests, lint, diagramas y procedimientos de reversión orientados principalmente a ingeniería.

ArqUX 0.8 debe separar definitivamente:

```text
GOBIERNO
de
DOMINIO
de
EJECUCIÓN
```

El kernel no debe saber si una actividad está comprando una computadora, desplegando un servicio, revisando un contrato o reparando una máquina.

Debe saber únicamente:

```text
qué se intenta conseguir
quién puede decidir
qué restricciones existen
qué trabajo está autorizado
qué efecto puede producirse
qué evidencia debe existir
cómo se determina el resultado
```

La semántica particular pertenece al dominio.

---

# 3. Principio rector de ArqUX 0.8

La filosofía central puede resumirse así:

> **El agente propone, razona y ejecuta capacidades. ArqUX determina bajo qué autoridad, contrato y condiciones esas acciones son válidas. El humano conserva la legitimidad última del gobierno.**

Esto conserva el principio fundacional de que la autoridad organizacional tiene origen y legitimación humana.

ArqUX no pretende limitar innecesariamente la autonomía de los agentes.

Pretende convertirla en **autonomía gobernada**.

Por tanto:

```text
Autonomía
≠ ausencia de control

Gobierno
≠ intervención humana en cada acción
```

La meta es que el agente disponga de toda la autonomía necesaria **dentro de un espacio de autoridad explícitamente válido**.

---

# 4. El nuevo objeto universal: Governed Activity

Una **Governed Activity** representa cualquier actividad que una organización considere suficientemente significativa como para exigir continuidad, responsabilidad o evidencia.

Una Activity puede ser pequeña:

```text
Obtener tres presupuestos para una reparación.
```

o extensa:

```text
Seleccionar, contratar e implementar un nuevo sistema ERP.
```

Puede durar minutos, meses o permanecer activa indefinidamente.

La Activity proporciona el marco causal superior:

```text
WHY
qué necesidad origina el trabajo
```

Dentro de ella pueden existir:

```text
Activity
   ↓
Cycle
   ↓
Blueprint
   ↓
Task
```

La **Task continúa siendo la unidad mínima gobernada de ejecución**, consistente con la definición fundacional actual.

Sin embargo, en 0.8 se diferencia entre:

```text
existencia lógica de la Task
y
materialización física de la Task
```

Una Task simple puede permanecer embebida dentro del Blueprint.

Una Task que necesite delegación independiente, ejecución prolongada, evidencia propia o integración con un sistema externo puede materializarse como artefacto independiente.

Esto elimina burocracia sin perder semántica.

---

# 5. De Project a Governed Space

El concepto `Project` debe dejar de ser una abstracción estructural obligatoria.

En operaciones empresariales muchas actividades no pertenecen a proyectos.

Pueden pertenecer a:

```text
un departamento
un cliente
un contrato
un activo
un servicio
un proceso
una sucursal
un expediente
una operación permanente
```

ArqUX 0.8 introduce conceptualmente:

## Governed Space

Un **Governed Space** es un límite de contexto y gobierno dentro del cual se desarrollan actividades.

Un Space puede declarar un tipo:

```text
project
process
department
service
asset
case
program
business-unit
custom
```

Por compatibilidad:

```text
Project = GovernedSpace(type=project)
```

Así no se destruye el modelo anterior.

Se generaliza.

La jerarquía puede convertirse en:

```text
Organization
      ↓
Workspace
      ↓
Governed Space
      ↓
Activity
      ↓
Cycle
      ↓
Blueprint
      ↓
Task
```

No todos los niveles necesitan materializarse en todas las actividades.

---

# 6. Blueprint 0.8: contrato, no plantilla fija

En ArqUX, un Blueprint adquiere naturaleza contractual cuando está suficientemente definido, cumple las condiciones de gobierno y recibe aprobación formal. Ese principio debe conservarse.

Pero en 0.8 debe distinguirse:

```text
Contract Model
≠
Contract Presentation
```

El contrato lógico universal debe contener, al menos:

| Dimensión   | Pregunta                                    |
| ----------- | ------------------------------------------- |
| Identity    | ¿Quién participa?                           |
| Purpose     | ¿Por qué existe esta actividad?             |
| Context     | ¿En qué realidad opera?                     |
| Scope       | ¿Qué está y qué no está autorizado?         |
| Authority   | ¿Quién puede hacer y decidir qué?           |
| Constraints | ¿Qué condiciones son obligatorias?          |
| Risk        | ¿Qué puede salir mal?                       |
| Tasks       | ¿Qué trabajo debe realizarse?               |
| Acceptance  | ¿Cómo se determina éxito?                   |
| Evidence    | ¿Qué prueba debe conservarse?               |
| Gates       | ¿Qué decisiones o controles son necesarios? |
| Closure     | ¿Qué condiciones permiten terminar?         |

La representación concreta procede de una plantilla aportada por el dominio.

Por ejemplo:

```text
software-feature
procurement
contract-review
incident-response
maintenance
market-research
expense-approval
customer-onboarding
```

El parser dinámico existente en ArqUX 0.7.8 ya demuestra que las secciones pueden descubrirse desde el Template sin estar codificadas en el parser.

0.8 debe llevar esta propiedad hasta su consecuencia arquitectónica completa.

---

# 7. Contract Freeze y Amendment

Una vez aprobado el Blueprint, sus elementos contractuales críticos quedan congelados.

Conceptualmente:

```text
Contract rev.4
     ↓
APPROVED
     ↓
FROZEN
```

Durante la ejecución se permite agregar:

```text
evidence
progress
observations
execution notes
measurements
findings
```

pero no modificar silenciosamente:

```text
objective
scope
constraints
authority
acceptance criteria
mandatory gates
```

Si el contexto obliga a cambiar el contrato:

```text
Amendment
   ↓
Contract rev.5
   ↓
re-evaluation
   ↓
approval
```

De este modo la evolución del trabajo queda explicada causalmente.

---

# 8. Gobierno proporcional

ArqUX 0.7 establece correctamente que la profundidad del gobierno debe ser proporcional al riesgo, impacto, criticidad, alcance, reversibilidad y regulación de la actividad.

La implementación 0.8 debe convertir ese principio en comportamiento operativo.

El usuario ya no debería tener que decidir:

```text
"¿Task o Blueprint?"
```

El flujo debe ser:

```text
Intent
  ↓
Read-only Discovery
  ↓
Context Resolution
  ↓
Risk / Impact Evaluation
  ↓
Governance Profile
  ↓
Contract Materialization
```

Se proponen cinco perfiles de gobierno:

| Perfil          | Naturaleza                                                               |
| --------------- | ------------------------------------------------------------------------ |
| G0 — Observe    | lectura, análisis o recomendación sin efecto                             |
| G1 — Compact    | trabajo pequeño, conocido, reversible y de bajo impacto                  |
| G2 — Governed   | actividad ordinaria que requiere contrato y evidencia                    |
| G3 — Assured    | riesgo o impacto elevado; requiere controles adicionales                 |
| G4 — Controlled | actividad regulada, sensible, irreversible o con segregación obligatoria |

El perfil no determina la importancia comercial de la actividad.

Determina la **cantidad mínima de gobierno necesaria para ejecutarla de forma segura y explicable**.

Un G1 puede generar internamente un Compact Contract de pocos campos.

Un G4 puede requerir múltiples Gates, evidencias independientes y segregación de funciones.

---

# 9. Discovery siempre precede a autorización

ArqUX 0.8 debe distinguir estrictamente:

```text
entender
de
cambiar
```

Antes de determinar el perfil de gobierno, el agente puede explorar contexto de forma read-only.

Esto amplía una propiedad que ArqUX 0.7.8 ya fortaleció al separar efectivamente operaciones de lectura y mutación.

Discovery puede incluir:

```text
lectura documental
consulta de sistemas
investigación
análisis de datos
identificación de restricciones
detección de dependencias
estimación de riesgo
```

Pero Discovery no confiere autoridad para actuar.

---

# 10. Authority Engine

El modelo de autorización simplificado de 0.7.8 basado principalmente en:

```text
governor
executor
auditor
```

debe evolucionar hacia el modelo conceptual que ArqUX ya había definido.

La autoridad efectiva debe ser consecuencia de:

```text
Participant
+ Identity
+ Role
+ Domain
+ Scope
+ Workflow Stage
+ Validity
+ Delegation
+ Directives
+ Contract
```

La Carta Fundacional ya define la autoridad como una intersección contextual de varios de estos factores.

El resultado de una evaluación de autoridad puede ser:

```text
allowed
denied
requires_approval
requires_separation
requires_evidence
expired
out_of_scope
```

La autoridad nunca debe inferirse de la competencia.

---

# 11. Capability ≠ Authority

Ésta debe convertirse en una invariante explícita.

Un agente puede disponer de:

```text
email.send
bank.transfer
filesystem.write
supplier.search
document.sign
database.update
```

sin estar autorizado a utilizarlas en una determinada actividad.

Por tanto:

```text
Skill
= capacidad

Capability
= operación posible

Authority
= derecho contextual a ejercerla
```

La Arquitectura de Referencia de ArqUX ya separa explícitamente Capability de Authority dentro de la ejecución gobernada.

0.8 debe llevar esa separación a todos los dominios.

---

# 12. Authority Lease

Para acciones de riesgo o efecto externo se introduce conceptualmente el **Authority Lease**.

Un Lease autoriza una acción concreta durante un contexto limitado.

Ejemplo:

```text
authority_id: AUTH-1044

actor: agent.procurement
action: supplier.order
subject: PO-882
scope: procurement
revision: 3
valid_until: 2026-10-02
uses: 1
```

Una vez utilizado:

```text
AUTH-1044
→ consumed
```

Esto evita que una autorización temporal termine convirtiéndose accidentalmente en privilegio permanente.

Puede utilizarse para:

```text
aprobar pagos
enviar comunicaciones
publicar contenido
modificar sistemas
aceptar contratos
cerrar actividades
```

---

# 13. Workflow Runtime

El Workflow no debe ser solamente un documento que el agente interpreta.

Debe existir un runtime determinista capaz de responder:

```text
¿cuál es el estado actual?
¿qué transiciones son válidas?
¿qué autoridad necesita cada transición?
¿qué condiciones deben cumplirse?
¿qué evidencia debe existir?
¿qué efecto produce la transición?
¿cómo se recupera una operación interrumpida?
```

Un Workflow debe poder declarar:

```text
State
Transition
Guard
Authority
Gate
Effect
Evidence
Timeout
Recovery
```

Ejemplo conceptual:

```text
active
  ↓ submit_for_review
reviewing
  ↓ accept
accepted
  ↓ conform
conformant
  ↓ close
closed
```

El agente puede solicitar:

```text
workflow.next()
```

pero no inventar unilateralmente una transición.

---

# 14. Execution ≠ Verification ≠ Acceptance ≠ Closure

Ésta debe convertirse en una corrección fundamental respecto a 0.7.8.

El código actual todavía contiene una semántica donde `blueprint.complete` representa simultáneamente ejecución completa y aprobación.

El propio modelo fundacional distingue estos conceptos.

0.8 establece:

```text
Executed
≠ Verified
≠ Accepted
≠ Conformant
≠ Closed
```

Una actividad puede estar correctamente ejecutada y no ser aceptada.

Puede ser aceptada funcionalmente y no ser conforme.

Puede ser conforme y todavía no reunir condiciones administrativas para cierre.

Estas diferencias resultan esenciales fuera del software.

---

# 15. Governed Subject Snapshot

Toda decisión importante debe referirse a un objeto exacto.

ArqUX 0.8 introduce el concepto de **Governed Subject Snapshot**.

Un Snapshot contiene como mínimo:

```text
subject_id
type
revision
canonical_digest
captured_at
provenance
```

Ejemplos:

Para software:

```text
repository tree
revision
digest
```

Para compras:

```text
quotation A rev2
quotation B rev4
budget rev1
comparison matrix rev3
```

Para un contrato:

```text
contract.pdf
revision 7
sha256
```

Para investigación:

```text
dataset
methodology
analysis model
report revision
```

Una aprobación no significa:

```text
"esto está aprobado"
```

Significa:

```text
"este snapshot específico está aprobado"
```

Cualquier modificación relevante genera otro Snapshot y puede invalidar decisiones anteriores.

---

# 16. Evidence Engine

Evidence deja de ser únicamente una anotación textual en PULSE.

ArqUX 0.8 debe tratar Evidence como una entidad gobernada.

Una Evidence puede declarar:

```text
evidence_id
subject
claim
criterion
producer
source
kind
content_ref
digest
produced_at
provenance
validation_status
validator
```

El contenido puede ser:

```text
documento
imagen
factura
medición
resultado de API
correo
acta
prueba automatizada
captura
métrica
firma
registro de sistema
```

El `brain.cortex` no necesita contener el artefacto pesado.

Puede conservar:

```text
identidad
referencia
digest
significado
provenance
```

El módulo actual de evidencia ya utiliza una traza append-only dentro de PULSE, lo que constituye una buena base de continuidad, pero todavía almacena esencialmente `task_id`, `kind`, `payload`, `agent` y `cycle`.

0.8 eleva esa traza a evidencia verificable.

---

# 17. Assurance Runtime

ArqUX 0.8 generaliza el concepto de review mediante **Assurance Lenses**.

Una Lens evalúa un Subject Snapshot desde una perspectiva determinada.

Según el dominio pueden existir:

| Dominio       | Lenses posibles                                     |
| ------------- | --------------------------------------------------- |
| Software      | seguridad, fiabilidad, arquitectura, pruebas        |
| Compras       | precio, proveedor, fraude, presupuesto              |
| Legal         | obligaciones, riesgo, jurisdicción, inconsistencias |
| Operaciones   | seguridad, procedimiento, calidad                   |
| Finanzas      | autorización, presupuesto, conciliación             |
| Investigación | metodología, fuentes, reproducibilidad              |
| Comercial     | mensaje, cumplimiento, marca, impacto               |

Varias Lenses pueden ejecutarse de manera independiente y luego producir un Assurance Result consolidado.

La revisión no otorga automáticamente autoridad de ejecución posterior.

---

# 18. Decisions como entidad explícita

ArqUX 0.8 debe registrar decisiones significativas como objetos causales.

Una Decision debería contener:

```text
decision_id
actor
authority
subject_snapshot
question
result
rationale
evidence_refs
governance_release
timestamp
```

Así pueden reconstruirse posteriormente preguntas como:

```text
¿quién aprobó esto?
¿con qué autoridad?
¿qué evidencia observó?
¿qué versión estaba evaluando?
¿qué reglas estaban vigentes?
```

Esta propiedad es esencial para operaciones empresariales reales.

---

# 19. Governance Release

Las reglas institucionales no pueden depender de definiciones mutables sin versión.

El Modelo Operativo ya establece que cada Cycle y Blueprint contractual debe identificar la Governance Release aplicable.

En 0.8 este principio se vuelve universal.

Una actividad debe poder ser reconstruida como:

```text
Activity ACT-18

Governance Release:
GOV-2026.09

Contract:
BLP-028 rev4

Workflow:
procurement.standard@2.1

Domain Pack:
procurement@1.4

Policies:
finance-policy@3.2
supplier-policy@1.8
```

Esto permite evolucionar la organización sin reescribir retrospectivamente su historia.

---

# 20. Domain Packs

El dominio abandona definitivamente el kernel.

Un **Domain Pack** puede proporcionar:

```text
templates
workflows
capabilities
risk models
evidence schemas
assurance lenses
skills
projections
policies
terminology
```

Ejemplos:

```text
arqux-domain-software
arqux-domain-procurement
arqux-domain-operations
arqux-domain-research
arqux-domain-legal
arqux-domain-finance
```

Una organización puede crear sus propios packs:

```text
company-sales
company-logistics
company-quality
```

Un Domain Pack no puede adjudicarse autoridad.

Puede declarar:

```text
purchase.approve
requires role purchase_approver
```

pero la organización determina quién posee ese rol.

---

# 21. Extension SPI

ArqUX 0.7.8 utiliza actualmente un registro estático de handlers.

0.8 requiere una verdadera interfaz de extensión.

El kernel debe permitir al menos estos proveedores:

```text
DomainProvider
WorkflowProvider
CapabilityProvider
EvidenceProvider
PolicyProvider
RiskProvider
AssuranceProvider
AdapterProvider
ProjectionProvider
```

Cada extensión declara:

```text
id
version
api_version
dependencies
capabilities
effects
authority_requirements
risk
idempotency
evidence_contract
```

Las extensiones amplían comportamiento.

No redefinen las invariantes del kernel.

---

# 22. External Effects

ArqUX 0.8 debe distinguir una operación interna de un efecto sobre el mundo.

Ejemplos:

```text
draft email
≠
send email

prepare payment
≠
transfer money

generate contract
≠
sign contract

prepare order
≠
place order
```

Toda Capability debe poder declarar su clase de efecto:

```text
none
local
internal
external
financial
legal
physical
public
irreversible
```

El perfil de gobierno y la autoridad pueden utilizar esa clasificación.

---

# 23. Idempotencia y recuperación

Toda ejecución que pueda provocar efectos debe poseer suficiente información para evitar duplicaciones.

Antes de una operación externa deberían persistirse, cuando corresponda:

```text
attempt_id
task
authority
idempotency_key
precondition
expected_effect
detection_strategy
recovery_strategy
```

La Arquitectura de Referencia ya contempla esta separación mediante `AttemptManager`, `ToolInvocationController`, `EffectObserver` y `RecoveryManager`.

La regla central es:

> **respuesta satisfactoria de una herramienta no equivale necesariamente a efecto aplicado.**

Esto resulta incluso más importante en operaciones comerciales y administrativas que en software.

---

# 24. Participant, Identity y Role

ArqUX 0.8 abandona definitivamente la asociación:

```text
Identity = personaje
```

Una Identity representa un contrato operativo.

Un Participant puede ser:

```text
human
agent
service
automation
organization
external actor
```

La relación Participant ↔ Identity es **muchos-a-muchos**:

```text
Un mismo Participant puede operar con varias Identities.
Una misma Identity puede ser adoptada por varios Participants.
```

El vínculo concreto no es estático: se resuelve por sesión y contexto
(binding = Participant + Identity + Role + Domain + Scope).

Una Identity puede asumir distintos Roles según el contexto.

Alfred, Jarvis, Seshat y Heimdall pueden continuar existiendo, pero como parte de un **Experience Pack predeterminado**, no como primitivas del kernel.

Una empresa puede definir:

```text
ProcurementAssistant
LegalReviewer
OperationsCoordinator
FinanceApprover
QualityAuditor
```

sin modificar ArqUX.

---

# 25. Agentes como participantes operacionales

En 0.8 un agente de IA deja de ser simplemente una interfaz conversacional.

Puede desempeñar distintos niveles de participación:

```text
Observer
Advisor
Planner
Executor
Reviewer
Coordinator
Monitor
```

pero dichos nombres describen funciones.

La autoridad concreta sigue dependiendo del contexto.

Un agente puede, por ejemplo:

```text
investigar proveedores
comparar precios
solicitar cotizaciones
preparar una orden de compra
```

y no disponer de autoridad para:

```text
emitir la orden
realizar el pago
```

Otro agente o persona puede ejercer esa decisión.

---

# 26. Human Sovereignty

ArqUX no debe convertirse en un sistema donde la autonomía técnica sustituya la legitimidad organizacional.

El humano puede delegar considerable autonomía.

Incluso puede permitir:

```text
autorización automática
aprobaciones bajo umbral
cierre automático
ejecución desatendida
```

pero dichas facultades deben proceder de políticas explícitas.

En consecuencia:

```text
Human Sovereignty
≠ Human Micromanagement
```

Significa:

> la capacidad del sistema para actuar autónomamente deriva de reglas cuya legitimidad pertenece finalmente a la organización humana.

---

# 27. Context y Memory

ArqUX mantiene su principio local-first.

El archivo conserva estado.

El agente colabora.

MCP y otros adaptadores sincronizan capacidades.

La Visión Empresarial ya articula esta relación.

0.8 mantiene diferentes horizontes de contexto:

```text
Institution
Workspace
Governed Space
Activity
Cycle
Blueprint
Task
Session
```

El contexto suministrado al agente debe ser mínimo pero suficiente.

No todo el conocimiento debe cargarse en cada sesión.

---

# 28. Learning

ArqUX no debe confundir memoria con aprendizaje institucional.

Un hallazgo producido durante una actividad puede evolucionar:

```text
observation
↓
local lesson
↓
project/space knowledge
↓
institutional candidate
↓
approved institutional knowledge
```

La promoción debe estar gobernada.

Así se evita que una conclusión accidental de un agente se convierta silenciosamente en regla de la organización.

---

# 29. Experience Layer

La potencia interna de ArqUX no debe trasladarse como complejidad al usuario.

El usuario debería poder decir:

```text
"Busca tres proveedores de cámaras y prepara una propuesta."
```

y ArqUX resolver:

```text
Activity
Domain
Governance Profile
Contract
Workflow
Capabilities
Authority
Evidence
```

sin exigir que la persona conozca esos términos.

La interacción humana debe operar principalmente sobre:

```text
intención
decisiones
excepciones
aprobaciones
resultados
```

No sobre mecanismos internos.

---

# 30. Aplicación práctica a operaciones de negocio

Ejemplo:

```text
"Necesitamos comprar cinco notebooks."
```

ArqUX podría resolver:

```text
Activity:
Adquisición de notebooks

Domain:
procurement

Profile:
G2 Governed

Contract:
cantidad
requisitos
presupuesto
criterios de selección

Tasks:
identificar proveedores
obtener presupuestos
normalizar ofertas
evaluar
preparar recomendación

Evidence:
cotizaciones
matriz comparativa
disponibilidad
garantía

Gate:
aprobación de compra

Authority:
agente puede investigar
agente puede solicitar cotizaciones
responsable financiero aprueba gasto
agente autorizado emite orden

Closure:
orden confirmada
factura registrada
recepción prevista
```

El mismo kernel puede gobernar:

```text
"Renueva el seguro del vehículo."
```

o:

```text
"Investiga por qué bajaron las ventas este mes."
```

o:

```text
"Coordina el mantenimiento preventivo del generador."
```

---

# 31. Arquitectura objetivo

La arquitectura lógica de ArqUX 0.8 puede representarse así:

```text
┌──────────────────────────────────────────────┐
│               EXPERIENCE LAYER               │
│ assistants · UI · CLI · MCP · API           │
├──────────────────────────────────────────────┤
│                DOMAIN PACKS                  │
│ procurement · software · legal · operations │
├──────────────────────────────────────────────┤
│               ASSURANCE RUNTIME              │
│ lenses · verification · compliance          │
├──────────────────────────────────────────────┤
│               WORKFLOW RUNTIME               │
│ states · transitions · guards · recovery    │
├──────────────────────────────────────────────┤
│                CONTRACT ENGINE               │
│ Blueprint · Tasks · Freeze · Amendment      │
├──────────────────────────────────────────────┤
│                AUTHORITY ENGINE              │
│ identity · role · scope · lease · delegation│
├──────────────────────────────────────────────┤
│                EVIDENCE ENGINE               │
│ claims · provenance · digest · snapshots    │
├──────────────────────────────────────────────┤
│             GOVERNANCE RESOLVER              │
│ G0 · G1 · G2 · G3 · G4                     │
├──────────────────────────────────────────────┤
│                ARQUX KERNEL                  │
│ Identity · Context · Contract · Decision    │
│ Execution · Evidence                        │
├──────────────────────────────────────────────┤
│                 ADAPTERS                     │
│ fs · email · ERP · CRM · tools · agents     │
└──────────────────────────────────────────────┘
```

---

# 32. Qué pertenece al Kernel

El Kernel debe permanecer pequeño.

Debe conocer:

| Responsabilidad    | Kernel |
| ------------------ | ------ |
| identidad          | sí     |
| contexto           | sí     |
| autoridad          | sí     |
| contrato           | sí     |
| workflow           | sí     |
| decisión           | sí     |
| evidence semantics | sí     |
| efectos            | sí     |
| auditoría          | sí     |
| gobierno           | sí     |
| compras            | no     |
| Git                | no     |
| tests              | no     |
| contratos legales  | no     |
| contabilidad       | no     |
| CRM                | no     |
| mantenimiento      | no     |

Ésta es la separación que hace posible la generalización.

---

# 33. Invariantes de ArqUX 0.8

ArqUX 0.8 debe considerarse arquitectónicamente conforme solamente si puede garantizar que:

1. ninguna ejecución significativa ocurre sin un contexto contractual válido;
2. capability nunca implica authority;
3. una lectura no produce mutación implícita;
4. toda mutación significativa puede vincularse a un actor y autoridad;
5. una modificación contractual posterior a aprobación genera una nueva revisión;
6. una decisión relevante referencia un Subject Snapshot exacto;
7. ejecución completa no implica automáticamente aceptación;
8. aceptación no implica automáticamente conformidad;
9. conformidad no implica automáticamente cierre;
10. una extensión puede añadir un dominio sin modificar el kernel;
11. un nuevo Workflow puede incorporarse sin crear handlers específicos;
12. un nuevo agente puede operar sin modificar el modelo de autoridad;
13. una organización puede reconstruir qué reglas estaban vigentes cuando ocurrió una decisión;
14. la evidencia conserva procedencia e integridad;
15. el nivel de gobierno es proporcional al riesgo y efecto de la actividad;
16. la autonomía de los agentes se mantiene dentro de autoridad explícita;
17. las operaciones externas son observables y recuperables;
18. el conocimiento institucional sólo se eleva mediante gobierno;
19. el usuario no necesita conocer la maquinaria interna para operar con ArqUX;
20. el mismo kernel puede gobernar actividades de múltiples dominios.

---

# 34. Compatibilidad con ArqUX 0.7

ArqUX 0.8 no debe negar la inversión realizada en 0.7.

Debe reinterpretarla.

```text
0.7 Project
→ Governed Space(type=project)

0.7 Blueprint
→ Contract Blueprint

0.7 Task
→ Contract Task

0.7 governor/executor/auditor
→ default organizational roles

0.7 BLP_TEMPLATE
→ software domain template

0.7 workflows.skill
→ software/default workflow provider

0.7 Evidence/PULSE
→ legacy evidence projection

0.7 identities
→ default Experience Pack
```

La compatibilidad debe permitir que un proyecto 0.7.8 continúe funcionando bajo 0.8 utilizando un:

```text
arqux-domain-software
```

que reproduzca inicialmente su comportamiento.

---

# 35. Relación con CORTEX

CORTEX no debe absorber semántica de dominio.

Debe continuar cumpliendo la función de representación, canonicalización, integridad y proyección.

La Especificación de Implementación ya establece conceptualmente que CODEC-CORTEX representa y canonicaliza mientras ArqUX interpreta autoridad, lifecycle y consecuencias.

Por tanto:

```text
CORTEX
= representation

ArqUX
= governance semantics
```

Esta separación debe preservarse estrictamente en 0.8.

---

# 36. ArqUX 0.8 como plataforma

La consecuencia final de esta evolución es que ArqUX deja de ser solamente una herramienta utilizada “dentro de proyectos”.

Puede convertirse en una infraestructura continua de asistencia organizacional.

Un agente gobernado por ArqUX podría colaborar diariamente en:

```text
leer comunicaciones
detectar obligaciones
preparar tareas
investigar alternativas
coordinar proveedores
actualizar sistemas
seguir vencimientos
analizar indicadores
preparar decisiones
ejecutar operaciones autorizadas
controlar resultados
generar evidencia
escalar excepciones
```

sin requerir que cada acción sea iniciada manualmente como una conversación independiente.

La organización define:

```text
qué puede observar
qué puede proponer
qué puede ejecutar
qué necesita aprobación
qué debe demostrar
qué debe escalar
```

Y ArqUX convierte esas definiciones en gobierno operativo.

---

# 37. Definición final

**ArqUX 0.8 es un sistema de gobierno operativo para organizaciones aumentadas por inteligencia artificial.**

No reemplaza al agente.

No reemplaza los sistemas empresariales.

No reemplaza los procesos de la organización.

Los conecta dentro de una estructura verificable de:

```text
contexto
autoridad
contrato
ejecución
evidencia
decisión
aprendizaje
```

Su misión es permitir que humanos y agentes trabajen con niveles crecientes de autonomía sin perder:

```text
control
trazabilidad
responsabilidad
continuidad
explicabilidad
capacidad de intervención
```

La transición esencial respecto de 0.7 puede expresarse así:

```text
ArqUX 0.7
Gobierno de agentes trabajando sobre proyectos

                ↓

ArqUX 0.8
Gobierno de actividades organizacionales
ejecutadas por humanos, agentes y sistemas
```

Y su principio operativo definitivo sería:

> **Toda actividad puede automatizarse hasta el límite que permita su autoridad, su riesgo y su contrato; nunca más allá.**

