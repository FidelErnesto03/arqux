# Framework de Gobernanza para Equipos de Agentes

Documento funcional completo. Describe el framework de gobernanza para equipos de agentes inteligentes: su visión, principios, capacidades y resultados esperados. No contiene referencias a tecnologías, lenguajes, protocolos ni implementaciones específicas; su propósito es permitir a un equipo de desarrollo y auditoría externo comprender el sistema en su totalidad y, si fuera necesario, reconstruirlo a partir de esta descripción.

---

## 1. Visión y propósito

El framework es una infraestructura de gobernanza que permite a equipos de agentes inteligentes trabajar de forma coordinada, trazable y auditada sobre proyectos complejos. Su objetivo funcional es:

- Garantizar que toda acción relevante quede registrada como evidencia.
- Impedir que un agente actúe fuera de su autoridad.
- Mantener un estado compartido y consistente entre agentes, proyectos y ciclos.
- Producir una memoria durable y consultable del conocimiento adquirido.
- Medir el tiempo de trabajo de forma automática y no intrusiva.
- Permitir la continuidad entre sesiones y agentes mediante handoffs estructurados.

El resultado deseado es un sistema donde cada decisión, tarea y lección queda encapsulada en artefactos verificables, y donde la gobernanza es una propiedad del proceso, no una tarea manual.

---

## 2. Principios fundamentales

1. **Gobernanza antes que ejecución**: ninguna acción de escritura ocurre sin autorización previa según el rol del agente.
2. **Evidencia obligatoria**: toda mutación de estado genera un registro en el rastro de evidencia.
3. **Contexto antes que conversación**: el primer contacto en un espacio gobernado siempre presenta el contexto del proyecto; nunca una mera salutación.
4. **Una fuente de verdad**: el estado compartido vive en un único artefacto por proyecto (el cerebro del proyecto), sincronizado con un cerebro de espacio de trabajo.
5. **Identidad verificada**: el agente autenticado es la única fuente de identidad; ningún parámetro presentado puede suplantarla.
6. **Medición automática y no dedicada**: el tiempo se registra como efecto interno de acciones naturales; no existen llamadas exclusivas para anotar tiempo.
7. **Lectura sin efectos**: las operaciones de lectura no mutan estado ni registran tiempo.
8. **Supresión gana**: si un artefacto fue eliminado por decisión autorizada, la captura pendiente se rechaza en lugar de recrearlo.
9. **Sin límites inventados**: si no hay sesión vinculada o la sesión está cerrada, el intervalo queda con cobertura limitada y no se fabrican marcas de tiempo.
10. **Roles inmutables por ejecución**: un agente no puede cambiar su rol dentro de una ejecución; el cambio de identidad es una acción explícita y auditada.

---

## 3. Arquitectura conceptual

El sistema se organiza en capas:

1. **Capa de acceso**: punto de entrada para agentes (interfaz conversacional y estructurada).
2. **Capa de gobernanza**: registro de manejadores, validación de permisos, aplicación de políticas.
3. **Capa de identidad y contexto**: resolución de agente, rol, proyecto, ciclo y sesión.
4. **Capa de estado**: persistencia del cerebro del proyecto y del espacio de trabajo.
5. **Capa de evidencia**: rastro inmutable de eventos.
6. **Capa de memoria**: aprendizaje, elevación de lecciones, conocimiento durable.
7. **Capa de medición**: timelog local por sesión.
8. **Capa de validación**: verificación de integridad y diagnóstico.

Cada capa es independiente y se comunica mediante contratos definidos. Un agente nunca accede directamente a la capa de estado; siempre a través de manejadores gobernados.

### 3.1 Núcleo de gobernanza vs. metodología de trabajo

El framework se divide en dos planos:

- **Núcleo de gobernanza (invariante)**: identidad y roles, sesiones, evidencia, registro de tiempo, memoria/cerebro, permisos, concurrencia, validación, respaldo. Este núcleo es el mismo independientemente de cómo se organice el trabajo. No depende de ninguna metodología particular.
- **Metodología de trabajo (intercambiable)**: la forma en que se estructura el trabajo —espacios, proyectos, ciclos, blueprints, tareas— es una metodología por defecto, no una propiedad del núcleo. El framework permite adoptar otra metodología de gobierno (por ejemplo, basada en epics/sprints, kanban, o flujos propios) siempre que respete los contratos del núcleo: toda acción significativa debe generar evidencia, toda mutación debe pasar por permisos, toda sesión debe tener registro de tiempo, y todo conocimiento debe persistir en el cerebro.

La metodología por defecto descrita en este documento (proyecto → ciclo → blueprint → tarea) es la que se establece al inicializar un espacio. Puede reemplazarse por otra, pero el núcleo de gobernanza permanece idéntico. Esto abre la puerta a que el mismo framework gobierne equipos con metodologías distintas sin cambiar su esencia.

---

## 4. Inicialización

### 4.1 Inicialización del espacio de trabajo

- **Resultado deseado**: crear el contenedor raíz que agrupa múltiples proyectos, con su cerebro propio, identidades, habilidades y registro de proyectos.
- **Acción**: inicializar el espacio de trabajo en un directorio raíz.
- **Efectos**:
  - Se crea la estructura de gobernanza del espacio.
  - Se genera un cerebro del espacio de trabajo (meta-cerebro) que indexa proyectos.
  - Se preparan directorios para identidades y habilidades.
  - Se registra un evento de bootstrap en el rastro de evidencia.
- **Validación posterior**: el diagnóstico debe reportar estructura completa y sin residuos.

### 4.2 Inicialización de un proyecto

- **Resultado deseado**: registrar un nuevo proyecto dentro del espacio de trabajo, con su propio cerebro, ciclos, tareas y agentes.
- **Acción**: inicializar un proyecto en un directorio y registrarlo en el meta-cerebro del espacio.
- **Efectos**:
  - Se crea la estructura de gobernanza del proyecto.
  - Se genera el cerebro del proyecto con secciones estándar.
  - Se registra el proyecto en el meta-cerebro con nombre, ruta y estado.
  - Se publica un evento de evidencia.
- **Precondición**: el espacio de trabajo debe existir.

### 4.3 Detección de contexto

- **Resultado deseado**: determinar si un directorio pertenece a un proyecto o a un espacio de trabajo, y a cuál.
- **Acción**: escanear hacia arriba desde una ruta buscando la marca de gobernanza.
- **Resultado**: indica encontrado/no encontrado, ruta y tipo (proyecto o espacio de trabajo).

### 4.4 Diagnóstico (doctor)

- **Resultado deseado**: verificar la salud del espacio o proyecto.
- **Comprobaciones**:
  - Ausencia de marcas de gobernanza anidadas (anomalía).
  - Estructura esperada presente.
  - Directorios huérfanos (sin escritor declarado).
  - Archivos residuales (respaldos, bloqueos).
  - Uso correcto de secciones de metadatos.
  - Integridad del cerebro del proyecto.
  - Ausencia de respaldos rastreados por control de versiones.
  - Correctitud de insignias de documentación.
- **Resultado**: lista de comprobaciones con estado (aprobado/advertencia/fallo) y resumen.

### 4.5 Validación de artefactos

- **Resultado deseado**: verificar la estructura e integridad de un archivo de memoria.
- **Acción**: validar un archivo contra el esquema del formato de memoria.
- **Resultado**: reporte de validez, duplicados, secciones faltantes.

---

## 5. Identidad y roles

### 5.1 Modelo de identidad

El sistema define identidades de agente como contratos de comportamiento. Cada identidad incluye:
- Nombre y rol.
- Reglas de comportamiento.
- Capacidades permitidas.
- Restricciones.

Las identidades se almacenan en el espacio de trabajo o en el paquete base, y se hidratan al iniciar una sesión.

### 5.2 Roles

Tres roles fundamentales:

- **Gobernador**: autoridad máxima. Puede inicializar espacios y proyectos, cancelar blueprints, re-delegar, registrar evidencia e identidad, y ejecutar acciones administrativas.
- **Ejecutor**: realiza el trabajo. Reclama tareas y blueprints, actualiza progreso, completa o falla tareas.
- **Auditor**: solo lectura. No puede escribir estado ni registrar tiempo. Observa y verifica.

### 5.3 Cambio de identidad (hot switch)

- **Resultado deseado**: cambiar la identidad activa de un agente en una sola llamada atómica.
- **Efectos**:
  - Se valida que la identidad destino exista.
  - Se hidrata el contrato completo.
  - Se registra un handoff y un evento de auditoría en el rastro de evidencia.
  - Se actualiza el contexto activo.
  - Se devuelve el encabezado formateado.
- **Soporta**: modo simulación (dry_run) y contenido estructurado.

### 5.4 Registro de lecciones de identidad

- **Resultado deseado**: registrar una lección conductual en el archivo de identidad del agente autenticado.
- **Restricción**: el agente_id explícito debe coincidir con el agente autenticado (no se permite suplantación).

### 5.5 Consulta de identidad

- **Resultado deseado**: obtener los datos de identidad de un agente desde el espacio de trabajo o desde el paquete base.
- **Agente por defecto**: el gobernador principal.

---

## 6. Espacio de trabajo y proyecto (metodología por defecto)

Nota: las entidades de espacio de trabajo y proyecto forman parte de la metodología por defecto. Otra metodología puede redefinir estas entidades, siempre que mantenga el núcleo de gobernanza.

### 6.1 Estado del espacio de trabajo

- **Resultado deseado**: obtener un resumen del estado del espacio de trabajo.
- **Información**: proyectos registrados, metadatos, estado de salud.
- **Formato**: mínimo por defecto; detallado bajo demanda.

### 6.2 Lecciones del espacio de trabajo

- **Resultado deseado**: listar las lecciones elevadas al meta-cerebro (conocimiento que trasciende proyectos).

### 6.3 Estado del proyecto

- **Resultado deseado**: obtener el estado activo del proyecto.
- **Información**: ciclos, tareas, agentes vinculados, estado de salud.

### 6.4 Vinculación de agente a proyecto

- **Resultado deseado**: asociar una identidad de agente a un proyecto con un rol.
- **Efecto**: el agente queda registrado como participante del proyecto.

### 6.5 Desvinculación de agente

- **Resultado deseado**: liberar la vinculación de un agente de un proyecto, sin dejar huérfanos.

### 6.6 Lecciones del proyecto

- **Resultado deseado**: listar las lecciones locales al proyecto.

---

## 7. Ciclos (metodología por defecto)

Nota: los ciclos son una entidad de la metodología por defecto. Otra metodología puede reemplazarlos por sus propias unidades de planificación.

Un ciclo es una unidad de trabajo temporal dentro de un proyecto, con objetivos, blueprints y tareas.

### 7.1 Creación de ciclo

- **Resultado deseado**: abrir un nuevo ciclo en el proyecto activo.
- **Efecto**: se crea el directorio del ciclo con su manifiesto.

### 7.2 Listado de ciclos

- **Resultado deseado**: listar los ciclos del proyecto, con su estado.

### 7.3 Ciclo actual

- **Resultado deseado**: obtener el ciclo activo del proyecto.

### 7.4 Cierre de ciclo

- **Resultado deseado**: cerrar un ciclo; no se pueden agregar nuevas tareas.
- **Efecto**: el manifiesto se marca como cerrado.

### 7.5 Reapertura de ciclo

- **Resultado deseado**: reabrir un ciclo cerrado para enmendar su manifiesto.

### 7.6 Síntesis de ciclo

- **Resultado deseado**: poblar las secciones del manifiesto del ciclo en una sola llamada (objetivos, blueprints, control points).

---

## 8. Blueprints (metodología por defecto)

Nota: los blueprints son artefactos de la metodología por defecto. Otra metodología puede usar sus propios artefactos de planificación.

Un Blueprint es el artefacto central de trabajo: un documento estructurado de 18 secciones que define un objetivo, precondiciones, procedimiento, criterios de aceptación, tareas y resultados. Es la unidad de planificación y ejecución.

### 8.1 Creación

- **Resultado deseado**: crear un nuevo Blueprint en estado borrador a partir de una plantilla.
- **Efecto**: se genera el archivo del Blueprint con las 18 secciones.

### 8.2 Declaración de listo

- **Resultado deseado**: el arquitecto declara el Blueprint listo para ejecución.
- **Transición**: borrador → listo.

### 8.3 Reclamo

- **Resultado deseado**: un ejecutor reclama el Blueprint.
- **Transición**: listo → en progreso.
- **Asignación implícita**: el ejecutor se resuelve a partir del agente_id (si el gobernador lo asigna), del ejecutor declarado, del contexto de sesión activo, o del agente autenticado.

### 8.4 Completado

- **Resultado deseado**: declarar la ejecución completa.
- **Transición**: en progreso → hecho (completado y aprobado en un paso).

### 8.5 Cancelación

- **Resultado deseado**: cancelar un Blueprint.
- **Transición**: cualquier estado → cancelado.
- **Restricción**: solo gobernador.

### 8.6 Falla

- **Resultado deseado**: marcar un Blueprint como bloqueado por un obstáculo.
- **Transición**: → bloqueado.

### 8.7 Re-delegación

- **Resultado deseado**: reabrir un Blueprint hecho o bloqueado tras una falla de verificación.
- **Uso**: corrección y reintento.

### 8.8 Bloqueo para revisión del arquitecto

- **Resultado deseado**: pausar la ejecución para revisión manual del arquitecto.

### 8.9 Ejecución (meta-manejador)

- **Resultado deseado**: ejecutar un Blueprint completo de forma orquestada.
- **Pasos**:
  1. Verificar precondiciones de la sección 3.
  2. Ejecutar las tareas de la sección 14 en secuencia.
  3. Verificar los criterios de aceptación de la sección 12.
  4. Marcar como completo.
- **Soporta**: modo simulación (dry_run).

### 8.10 Actualización de progreso

- **Resultado deseado**: actualizar el progreso del Blueprint con una nota o refinar una sección individual.

### 8.11 Lectura

- **Resultado deseado**: leer un Blueprint completo.
- **Formatos**: legible para humanos o estructurado para máquinas.

### 8.12 Listado

- **Resultado deseado**: listar Blueprints con filtros opcionales.
- **Paginación**: límite + desplazamiento; reporta total, devueltos, desplazamiento, siguiente desplazamiento.

### 8.13 Verificación de criterio de aceptación

- **Resultado deseado**: verificar un criterio de aceptación específico de la sección 12.

### 8.14 Actualización de tarea del Blueprint

- **Resultado deseado**: actualizar el checkbox de una tarea de la sección 14.
- **Estados**: en progreso / completado.

### 8.15 Actualización de frontmatter

- **Resultado deseado**: establecer o reparar escalares del frontmatter (título, ciclo).
- **Camino sancionado**: la única vía de escritura para campos que ningún otro manejador puede establecer.
- **Derivación**: si se omite el título, se deriva del marcador/cabecera del cuerpo.

### 8.16 Síntesis (modo guía)

- **Resultado deseado**: crear o encontrar el Blueprint y devolver la siguiente sección pendiente.
- **Efecto**: el agente escribe las secciones mediante actualizaciones; el Blueprint se crea y persiste si no existe.

---

## 9. Tareas (metodología por defecto)

Nota: las tareas son unidades de la metodología por defecto. Otra metodología puede redefinirlas.

Las tareas son unidades de trabajo dentro de un ciclo, con precondiciones, procedimiento, criterios de aceptación y asignación.

### 9.1 Creación

- **Resultado deseado**: crear una tarea gobernada en el ciclo actual.
- **Contenido estructurado**: acepta un bloque estructurado con objetivo, precondiciones, procedimiento, criterios de aceptación, bloqueadores, asignado, complejidad y prioridad.
- **Regla de fusión**: el contenido estructurado prevalece sobre parámetros individuales.

### 9.2 Reclamo

- **Resultado deseado**: un ejecutor reclama una tarea.
- **Transición**: → en progreso.

### 9.3 Completado

- **Resultado deseado**: marcar una tarea como hecha y registrar evidencia.

### 9.4 Falla

- **Resultado deseado**: marcar una tarea como bloqueada y registrar la causa.

### 9.5 Actualización

- **Resultado deseado**: actualizar el progreso de una tarea, opcionalmente cambiar estado.

### 9.6 Lectura

- **Resultado deseado**: leer una tarea en formato legible o estructurado.

### 9.7 Listado

- **Resultado deseado**: listar tareas con filtros.
- **Paginación**: límite + desplazamiento.

### 9.8 Ejecución (meta-manejador)

- **Resultado deseado**: ejecutar una tarea gobernada de forma orquestada.
- **Pasos**: verificar precondiciones, ejecutar pasos del procedimiento, marcar completo o fallar.
- **Soporta**: modo simulación.

---

## 10. Evidencia

La evidencia es el rastro inmutable de eventos del sistema. Cada acción relevante genera una entrada con identificador, marca de tiempo, agente, tipo y carga útil.

### 10.1 Registro

- **Resultado deseado**: agregar una entrada al rastro de evidencia en el cerebro del proyecto.

### 10.2 Consulta

- **Resultado deseado**: consultar el rastro de evidencia con filtros y paginación.

### 10.3 Lectura individual

- **Resultado deseado**: leer un evento de evidencia por su identificador.

---

## 11. Sesiones

Una sesión es la unidad de trabajo continua de un agente sobre un proyecto. Incluye identidad, contexto (proyecto + alcance), blueprints activos, resumen portable y registro de tiempo.

### 11.1 Bootstrap

- **Resultado deseado**: iniciar una sesión en un espacio o proyecto.
- **Comportamiento**:
  - Sin proyecto seleccionado: presenta el espacio de trabajo con proyectos disponibles, habilidades e identidad; no auto-selecciona proyecto.
  - Dentro de un proyecto: presenta proyecto, ciclo activo, blueprints.
  - Dentro de un ciclo: presenta manifiesto y todos los blueprints con estado.
- **Salidas**: contexto estructurado (máquina) y tablero (humano).
- **Regla**: contexto antes de conversación; nunca solo un saludo.
- **Auditoría**: se registra un evento de bootstrap en el rastro de evidencia.
- **Identidad**: la identidad autenticada es autoritativa; un agente_id explícito debe coincidir.

### 11.2 Establecer contexto

- **Resultado deseado**: establecer el puntero de contexto de la sesión (proyecto + alcance + blueprint opcional) y abrir o re-adjuntar la sesión real vinculada a la ejecución.
- **Efectos**:
  - Localiza el espacio de trabajo.
  - Resuelve el proyecto desde el meta-cerebro.
  - Valida que el proyecto tenga cerebro.
  - Abre o re-adjunta la sesión real para la ejecución.
  - Escribe el contexto por ejecución (archivo propio, sin sobrescribir otras ejecuciones).
  - Abre el bloque de tiempo de la sesión.
- **Restricción**: sin vinculación de ejecución, se rechaza.
- **Intención**: `new` (abre/recupera) o `resumed` (re-adjunta sin cambiar id ni inicio original; requiere referencia explícita).

### 11.3 Obtener contexto

- **Resultado deseado**: leer el puntero de contexto actual.
- **Comportamiento**: prefiere el archivo de contexto de la ejecución; cae al espacio compartido solo si no hay archivos por ejecución.

### 11.4 Cierre

- **Resultado deseado**: cerrar la sesión y escribir un resumen portable en el rastro de evidencia.
- **Selección de sesión**: por referencia explícita, o por sesión vinculada a la ejecución. Nunca adopta la sesión más reciente de otro ejecutor en una mutación.
- **Efectos**:
  - Construye el payload SES (resumen, blueprints, tareas, decisiones, brechas, conteo de lecciones).
  - Valida tamaño (< 2KB).
  - Registra el evento de sesión en el rastro de evidencia.
  - Captura el cierre del bloque de tiempo.
  - Marca la sesión como liberada.
  - Compacta las entradas del rastro de la sesión.
- **Alerta**: si el cierre ocurre sin sesión vinculada, se emite una advertencia de tiempo no registrado y se registra un evento de auditoría.

### 11.5 Reanudación

- **Resultado deseado**: restaurar el contexto de una sesión.
- **Comportamiento**: solo lectura; no escribe ni reabre. Selecciona por referencia explícita o por sesión vinculada a la ejecución; rechaza selección ambigua.

### 11.6 Estado

- **Resultado deseado**: leer metadatos de la sesión sin restaurar contexto completo.
- **Información**: estado, fechas de apertura/cierre, registro de tiempo, agente, proyecto, alcance, blueprints, resumen.

### 11.7 Handoff

- **Resultado deseado**: serializar el contexto de la sesión actual y escribir un handoff para un agente destino.
- **Efectos**:
  - Construye un payload estructurado con origen, destino, proyecto, resumen, blueprints y tareas.
  - Escribe el archivo de handoff en el directorio de handoffs.
  - Registra un evento de handoff en el rastro de evidencia.
- **Soporta**: modo simulación.

### 11.8 Compactación de pulsos

- **Resultado deseado**: compactar las entradas del rastro asociadas a una sesión.
- **Comportamiento**: por membresía de sesión (no por posición), poda entradas no-SES, escribe una lección consolidada.
- **Soporta**: modo simulación.

---

## 12. Registro de tiempo (timelog)

El registro de tiempo es local, por sesión, y automático. Mide minutos reales, no estimaciones.

### 12.1 Estructura

- Cada sesión tiene un archivo de registro de tiempo canónico.
- Contiene: identidad (proyecto, sesión, apertura, versión, revisión), actividades (bloques con inicio, fin, estado, revisión, nota, autorización) y recibos (proyecciones externas).

### 12.2 Bloques de actividad

- **Un bloque por actividad**: cada boundary de gobernanza (apertura/cierre de sesión, reclamo de tarea, cambio de identidad, etc.) genera un bloque con su intervalo.
- **Misma actividad, mismo bloque**: múltiples eventos sobre la misma actividad actualizan la evidencia existente; no agregan bloques.
- **Lectura no registra**: las operaciones de solo lectura no crean bloques.
- **Sin timers**: las marcas de tiempo provienen del instante UTC de la acción observada; no hay hilos contadores ni pulsos periódicos.
- **Sin límites inventados**: sin sesión vinculada, el intervalo queda con cobertura limitada y no se fabrican marcas.

### 12.3 Consulta

- **Resultado deseado**: consultar el registro de tiempo de una sesión o proyecto.
- **Información**: bloques, duraciones, estado, cobertura.

### 12.4 Proyección

- **Resultado deseado**: proyectar el registro de tiempo a un sistema externo de registro de horas.
- **Comportamiento**: genera recibos con estado (pendiente/confirmado); la copia remota nunca se edita desde el framework.

### 12.5 Revisión (corrección autorizada)

- **Resultado deseado**: corregir un bloque de tiempo con razón y autorización explícita.
- **Efecto**: escribe una nueva revisión con nota y referencia de autorización; los recibos previamente proyectados quedan obsoletos.

### 12.6 Purga

- **Resultado deseado**: purgar registros de tiempo según criterios autorizados.

### 12.7 Invalidación de pendientes

- **Resultado deseado**: marcar todos los bloques abiertos como explícitamente no terminados.

---

## 13. Memoria y estado (cerebro)

El cerebro es el artefacto de memoria estructurada del proyecto. Usa un formato de secciones con entradas tipadas (sigilos).

### 13.1 Lectura

- **Resultado deseado**: leer y parsear un archivo de memoria.
- **Modos**: estructurado (máquina) o legible (humano).

### 13.2 Escritura atómica

- **Resultado deseado**: escribir un archivo de memoria de forma atómica desde texto fuente.

### 13.3 Verificación

- **Resultado deseado**: verificar la estructura de un archivo de memoria.

### 13.4 Formato (transformación)

- **Resultado deseado**: transformar contenido entre formato máquina y legible.

### 13.5 Entradas (CRUD)

- **Obtener**: leer entradas que coincidan con un selector.
- **Agregar**: agregar una nueva entrada a una sección.
- **Actualizar**: modificar una entrada seleccionada.
- **Eliminar**: borrar una entrada.
- **Mover**: mover una entrada entre secciones.
- **Listar**: listar entradas con filtros y paginación.

### 13.6 Validación de archivo

- **Resultado deseado**: escanear un archivo de memoria en busca de entradas duplicadas y opcionalmente repararlas.

### 13.7 Compactación de basura (gc)

- **Resultado deseado**: eliminar o renombrar entradas duplicadas.
- **Modos**: deduplicar (elimina extras) o renombrar (preserva todos con nuevos ids secuenciales).
- **Soporta**: modo simulación.

### 13.8 Checkpoint

- **Resultado deseado**: persistir el estado de trabajo actual (foco, objetivos, tareas, estado) como una línea en el cerebro.

### 13.9 Migración

- **Resultado deseado**: aplicar una transformación nombrada a un archivo de memoria.
- **Soporta**: modo simulación.

### 13.10 Parcheo masivo

- **Resultado deseado**: aplicar múltiples cambios a entradas desde un payload estructurado.
- **Soporta**: modo simulación.

### 13.11 Renderizado

- **Resultado deseado**: renderizar un archivo de memoria a formato legible.
- **Diagramas**: renderizar diagramas de flujo a imágenes (requiere herramienta externa).

### 13.12 Referencia de sigilos

- **Resultado deseado**: obtener la definición de un sigilo (nombre, tipo, riesgo, capa, descripción) o el mapa de secciones estándar.

### 13.13 Aprendizaje (motor de aprendizaje)

- **Resultado deseado**: escanear el cerebro del proyecto y obtener entradas puntuadas y candidatos a elevación.
- **Elevación**: elevar una lección de evidencia a lección durable, o de lección a conocimiento. Por defecto es simulación; para aplicar se requiere confirmación con hash revisado.

---

## 14. Problemas (issues)

### 14.1 Creación

- **Resultado deseado**: reportar un nuevo problema en el proyecto con severidad (baja/media/alta/bloqueante) y un evento en el rastro de evidencia.

### 14.2 Listado

- **Resultado deseado**: listar problemas, opcionalmente filtrados por estado.

### 14.3 Lectura

- **Resultado deseado**: leer un problema por su identificador.

### 14.4 Actualización

- **Resultado deseado**: actualizar estado/severidad de un problema con transición trazada en el rastro de evidencia.
- **Restricción**: el estado "verificado" requiere referencia de auditoría (el evento del veredicto del auditor).

---

## 15. Protocolo de gobernanza

### 15.1 Adopción

- **Resultado deseado**: incorporar un agente con un rol al sistema.

### 15.2 Onboarding (alias)

- **Resultado deseado**: equivalente a adopción, para compatibilidad de flujos.

### 15.3 Pausa

- **Resultado deseado**: suspender la gobernanza de la sesión actual sin perder estado.

### 15.4 Reanudación

- **Resultado deseado**: reanudar la gobernanza tras una pausa.

### 15.5 Liberación

- **Resultado deseado**: desvincular completamente un agente (salida limpia, sin huérfanos).

---

## 16. Sincronización

### 16.1 Sincronización manual

- **Resultado deseado**: sincronizar el cerebro del proyecto al meta-cerebro con métricas completas.

### 16.2 Reconciliación

- **Resultado deseado**: reconciliar el cerebro con la realidad del sistema de archivos.
- **Niveles**: a nivel de ciclo o a nivel de proyecto.

---

## 17. Habilidades (skills)

Las habilidades son módulos de conocimiento reutilizables que guían el comportamiento de los agentes.

### 17.1 Listado

- **Resultado deseado**: listar todas las habilidades disponibles.

### 17.2 Obtención

- **Resultado deseado**: leer una habilidad por nombre, subruta o nombre anidado único.
- **Comportamiento**: devuelve contenido con guía accionable si no se encuentra o es ambiguo.

### 17.3 Edición

- **Resultado deseado**: leer, escribir o editar por sección un archivo de habilidad.
- **Modos**: reemplazo completo o edición de sección específica.

### 17.4 Conversión

- **Resultado deseado**: convertir una habilidad de formato original a formato ultra-denso.

### 17.5 Importación

- **Resultado deseado**: adquirir una habilidad de fuente externa y almacenar el original.

### 17.6 Instalación (meta-manejador)

- **Resultado deseado**: importar + validar + registrar en el cerebro.
- **Soporta**: modo simulación.

### 17.7 Evolución

- **Resultado deseado**: aplicar una adaptación aprobada a una habilidad.
- **Por defecto**: simulación.

### 17.8 Registro de desviación

- **Resultado deseado**: registrar una desviación cuando una habilidad no coincide con el contexto real.

---

## 18. Identidad (manejadores)

### 18.1 Consulta de identidad

- **Resultado deseado**: obtener datos de identidad de un agente desde el espacio de trabajo o el paquete base.

### 18.2 Cambio de identidad (hot switch)

- **Resultado deseado**: cambiar la identidad activa en una llamada atómica.
- **Efectos**: valida existencia, hidrata contrato, registra handoff y auditoría, actualiza contexto, devuelve encabezado.
- **Soporta**: contenido estructurado y modo simulación.

### 18.3 Registro de lección conductual

- **Resultado deseado**: registrar una lección en el archivo de identidad del agente autenticado.
- **Restricción**: el agente_id explícito debe coincidir con el autenticado.

---

## 19. Contexto

### 19.1 Detección

- **Resultado deseado**: escanear hacia arriba desde una ruta para encontrar la marca de gobernanza.

### 19.2 Contexto completo

- **Resultado deseado**: devolver el contexto completo del proyecto: nombre, ciclos disponibles, ciclo actual, agentes vinculados, habilidades disponibles.

---

## 20. Descubrimiento de manejadores

### 20.1 Listado

- **Resultado deseado**: descubrir manejadores disponibles clasificados por módulo, filtrados por nivel (básico/estándar/completo).
- **Paginación**: límite + desplazamiento.

### 20.2 Guía por intención

- **Resultado deseado**: obtener una guía curada de secuencia de manejadores para una intención, desde el corpus de guías.
- **Comportamiento**: si no hay coincidencia, devuelve temas disponibles y pistas.

---

## 21. Memoria de comunicación (comms)

### 21.1 Puente de comunicación

- **Resultado deseado**: enviar y recibir mensajes entre agentes o canales externos.

### 21.2 Configuración

- **Resultado deseado**: configurar canales de comunicación (token, endpoints).

### 21.3 Bandeja de entrada

- **Resultado deseado**: leer mensajes entrantes.

### 21.4 Doctor de comunicaciones

- **Resultado deseado**: verificar dependencias y tokens de comunicación.

### 21.5 Servidor de comunicaciones

- **Resultado deseado**: iniciar el servidor de comunicaciones sobre entrada/salida estándar.

---

## 22. Voz (subsistema opcional)

Subsistema para interacción por voz, desacoplado del núcleo.

### 22.1 Captura y procesamiento

- **Resultado deseado**: capturar audio, detectar actividad de voz, transcribir y sintetizar respuesta.

### 22.2 Daemon de voz

- **Resultado deseado**: controlar el daemon persistente de voz.

### 22.3 Reuniones

- **Resultado deseado**: gestionar sesiones de reunión con transcripción.

### 22.4 Métricas y compuerta

- **Resultado deseado**: medir latencia y aplicar compuertas de calidad.

### 22.5 Doctor de voz

- **Resultado deseado**: verificar dispositivos, dependencias y entorno de voz.

---

## 23. Respaldo y restauración

### 23.1 Respaldo

- **Resultado deseado**: crear un archivo comprimido del directorio de gobernanza con marca de tiempo.

### 23.2 Restauración

- **Resultado deseado**: restaurar el directorio de gobernanza desde un respaldo.
- **Comportamiento**: respalda el estado actual antes de restaurar.

---

## 24. Permisos y seguridad

### 24.1 Modelo de roles

- Tres roles: gobernador, ejecutor, auditor.
- El gobernador tiene autoridad total; el ejecutor realiza trabajo; el auditor solo lee.

### 24.2 Manejadores exclusivos del gobernador

- Inicialización de espacio y proyecto.
- Cancelación de blueprints.
- Re-delegación.

### 24.3 Manejadores que mutan estado

- Lista de manejadores que modifican estado, usada para control de acceso.

### 24.4 Manejadores condicionales

- Algunos manejadores mutan solo bajo ciertas condiciones.

### 24.5 Firma HMAC

- Ciertas acciones críticas (registro de identidad, registro de evidencia, re-delegación) requieren firma HMAC para garantizar autenticidad.

### 24.6 Variables de entorno

- La identidad del agente, el rol, la clave de ejecución y la raíz del proyecto se resuelven desde el entorno o desde el contexto autenticado.

### 24.7 Seguridad de archivos

- Escrituras atómicas.
- Bloqueos de archivo para concurrencia.
- Validación de rutas para evitar escapes del directorio de gobernanza.

---

## 25. Concurrencia

- **Bloqueo de cerebro**: exclusión mutua para mutaciones del cerebro del proyecto.
- **Bloqueo de archivo**: bloqueo reentrante por archivo de registro de tiempo.
- **Versión de concurrencia**: cada mutación incrementa la versión de concurrencia del cerebro.

---

## 26. Flujo funcional completo (de inicialización a cierre)

1. **Inicializar espacio de trabajo** → estructura raíz + meta-cerebro.
2. **Inicializar proyecto** → cerebro del proyecto + registro en meta-cerebro.
3. **Bootstrap de sesión** → contexto + tablero + evento de auditoría.
4. **Establecer contexto** → vincular sesión a proyecto/alcance + abrir bloque de tiempo.
5. **Crear ciclo** → unidad de trabajo.
6. **Crear blueprints y tareas** → planificación.
7. **Declarar listo** → aprobación del arquitecto.
8. **Reclamar y ejecutar** → trabajo del ejecutor, con registro automático de tiempo.
9. **Registrar evidencia** → cada acción significativa queda trazada.
10. **Cerrar tareas y blueprints** → completado.
11. **Cerrar ciclo** → no más tareas.
12. **Escalar lecciones** → memoria durable.
13. **Cerrar sesión** → resumen portable + compactación + cierre de bloque de tiempo.
14. **Handoff** → transferencia a otro agente si es necesario.
15. **Sincronizar y reconciliar** → consistencia entre cerebro y sistema de archivos.
16. **Diagnosticar** → verificación de salud.
17. **Respaldar** → archivo comprimido con marca de tiempo.

---

## 27. Resultados funcionales esperados

Al operar el framework, un equipo obtiene:

- Un **rastro de evidencia completo** de toda acción gobernada.
- **Memoria durable** con lecciones escaladas a conocimiento.
- **Medición automática de tiempo** sin intervención manual.
- **Continuidad entre sesiones y agentes** mediante handoffs y resúmenes portables.
- **Control de acceso por rol** con auditoría de cambios de identidad.
- **Consistencia** entre cerebro del proyecto y sistema de archivos.
- **Diagnóstico proactivo** de salud y residuos.
- **Recuperación** mediante respaldos y restauración.
- **Escalabilidad** de conocimiento mediante el motor de aprendizaje.

---

## 28. Glosario funcional

- **Agente**: entidad autónoma que actúa dentro del sistema.
- **Espacio de trabajo**: contenedor raíz de múltiples proyectos.
- **Proyecto**: unidad de trabajo con cerebro propio.
- **Ciclo**: período de trabajo dentro de un proyecto.
- **Blueprint**: artefacto de planificación y ejecución de 18 secciones.
- **Tarea**: unidad de trabajo dentro de un ciclo o blueprint.
- **Sesión**: período continuo de trabajo de un agente sobre un proyecto.
- **Cerebro**: artefacto de memoria estructurada.
- **Meta-cerebro**: cerebro del espacio de trabajo que indexa proyectos.
- **Evidencia**: rastro inmutable de eventos.
- **Lección**: conocimiento derivado de la experiencia, elevable a conocimiento durable.
- **Sigilo**: tipo de entrada en el cerebro (identidad, objetivo, trabajo, etc.).
- **Handoff**: transferencia estructurada de contexto entre agentes.
- **Bloque de tiempo**: intervalo de una actividad en el registro de tiempo.
- **Cobertura**: grado de confianza del intervalo (completa o limitada).
- **Gobernador/Ejecutor/Auditor**: roles fundamentales del sistema.