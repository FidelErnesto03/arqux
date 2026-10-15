# CYCLE-14 — Revisión del diseño de registro nativo de actividades y tiempos

Fecha: 14 de octubre de 2026. Proyecto: ARQUX.
Redacción y verificaciones documentales: Alfred. Auditor independiente: Heimdall.
Estado: diseño revisado; ciclo y seis BLPs en borrador; implementación no autorizada ni ejecutada.

## Resultado

Heimdall releyó las seis BLPs mediante MCP, con proyecto y ciclo explícitos, y concluyó que son documentalmente adecuadas para abordar los objetivos acordados. No quedaron hallazgos materiales abiertos tras el ciclo de corrección y relectura.

Este veredicto acredita diseño documental, no implementación, cumplimiento funcional ni permiso para ejecutar. Los criterios de aceptación y las tareas permanecen sin marcar; las compuertas de implementación no se han aprobado.

## Artefactos y orden

Documento rector: [.arqux/cycles/CYCLE-14/MANIFEST.md](../../.arqux/cycles/CYCLE-14/MANIFEST.md).

| BLP | Alcance | Dependencias |
| --- | --- | --- |
| [BLP-001](../../.arqux/cycles/CYCLE-14/blueprints/BLP-001.md) | Identidad SES y ciclo de vida aislado de sesión | Ninguna BLP del ciclo |
| [BLP-002](../../.arqux/cycles/CYCLE-14/blueprints/BLP-002.md) | Contrato y persistencia CORTEX del timelog | BLP-001 |
| [BLP-003](../../.arqux/cycles/CYCLE-14/blueprints/BLP-003.md) | Captura embebida en acciones de gobierno | BLP-002 |
| [BLP-004](../../.arqux/cycles/CYCLE-14/blueprints/BLP-004.md) | Consulta, corrección y depuración por el usuario | BLP-002 y BLP-003 |
| [BLP-005](../../.arqux/cycles/CYCLE-14/blueprints/BLP-005.md) | Integración en skill matriz y adopción | BLP-003 y BLP-004 |
| [BLP-006](../../.arqux/cycles/CYCLE-14/blueprints/BLP-006.md) | Proyección externa opcional y reconciliación | BLP-004 y BLP-005 |

La relación completa de objetivos está declarada en la sección 2 de cada BLP. La declaración principal explícita permite al reconciliador construir su índice sin adivinar objetivos desde la prosa.

## Cobertura de objetivos

| Objetivo | Resultado que debe alcanzar la implementación futura | Cobertura |
| --- | --- | --- |
| 1 | SES real desde apertura, inicio y ruta estables al reanudar | BLP-001 AC-01/02/03 |
| 2 | Aislamiento de ejecuciones y continuidad/compactación por pertenencia SES | BLP-001 AC-04/05/06; BLP-002 AC-03 |
| 3 | Persistencia recuperable solo .cortex, sin dependencias nuevas | BLP-002 AC-01 a AC-06 |
| 4 | Captura en acciones naturales autorizadas, sin cronómetro ni llamadas rutinarias exclusivas | BLP-003 AC-01 a AC-07 |
| 5 | Cálculo posterior UTC reproducible sin doble conteo ni tiempos inventados | BLP-004 AC-01/02/03 |
| 6 | Corrección y depuración plenamente controladas por el usuario, incluso sin exportación previa | BLP-004 AC-04/05/06; BLP-006 AC-06 |
| 7 | Instrucciones y distribución en skill matriz existente, sin crear o modificar AGENTS ni crear skills | BLP-005 AC-01 a AC-06 |
| 8 | Proyección autorizada, agnóstica y reconciliable que no elimina el origen | BLP-006 AC-01 a AC-07 |
| 9 | Unidad funcional usuario-agente y costo de registro acotado y medible | BLP-003 AC-04/05/06; BLP-004 AC-07; BLP-005 AC-04 |
| 10 | Verificación integral, regresión, permisos y recuperación con auditoría independiente | Todas las BLPs AC-08 y revisión documental actual |

Archivo acordado: `<proyecto>/.arqux/timelog/SESXXX_yyyymmdd_hhmiss.cortex`. La referencia SES procede del brain real; la fecha-hora de apertura original se conserva. El diseño explicita UTC para evitar ambigüedad y permite presentación local.

## Hallazgos incorporados en el loop Alfred–Heimdall

| Hallazgo | Resolución de diseño |
| --- | --- |
| La implementación vigente asigna evidencia de sesión al cierre, sin SES de apertura estable | BLP-001 establece identidad SES real en el vínculo natural autorizado al proyecto y recuperación por esa identidad |
| Puntero global, reanudación por último evento y compactación por posición | BLP-001 aísla contexto por ejecución y atribuye eventos/compactación mediante pertenencia explícita |
| Reemplazo atómico insuficiente, backups no CORTEX y posible falla entre brain y archivo | BLP-002 exige exclusión del ciclo lectura-modificación-escritura, revisión, auxiliares .cortex y fases recuperables; no promete atomicidad entre dos archivos |
| Captura podía ampliar permisos de lector o escribir sin señales suficientes | BLP-003 separa registrador autorizado y lectores; condiciona ambos puntos de captura a autoridad, cobertura y ausencia de supresión |
| Carrera de depuración contra captura o respuesta remota | BLP-002/003/004/006 comparten bloqueo y orden; revalidan supresión, invalidan pendientes y no recrean contenido por recibos tardíos |
| Depurar podía quedar condicionado a terminar una API | BLP-004/006 no retienen bloqueo durante red, no esperan red para depurar ni prometen cancelar una solicitud ya despachada |
| Clave destino/origen/revisión insuficiente si cambia una transformación | BLP-006 identifica lote exacto por orígenes/revisiones, selección, destino/cuenta/target, versión de adaptador/mapeo y contenido transformado con sus reglas |
| Exclusión genérica de pulsos podía confundirse con PULSE de gobierno | Se excluyen pulsos periódicos dedicados a medir tiempo, no la evidencia natural de gobierno |
| Riesgo de ampliar el alcance a nuevos contratos de agente | Ningún AGENTS.md ni plantilla AGENTS se crea o modifica; la adopción usa la skill matriz existente |

## Verificaciones realizadas

Alfred verificó mediante lectura MCP la coincidencia de las 18 secciones redactadas de cada BLP con su contenido persistido. Heimdall realizó su propia lectura de las seis BLPs y releyó las correcciones materiales.

Totales documentales: 108 secciones, 48 criterios de aceptación, 30 tareas propuestas y 18 diagramas. No hay casillas de ejecución marcadas. Los seis handlers de guía devolvieron `next_section=None`; esto indica redacción completa, no aceptación funcional ni autorización de ejecución.

Los 18 diagramas PlantUML se compilaron, incluidas las correcciones, con el JAR ya instalado y salida de proceso 0. Las fuentes validadas son las incluidas en las BLPs. No se instaló tecnología adicional. La validación fue ejecutada por Alfred, no independientemente por Heimdall.

El renderizador MCP no pudo usar su JAR por permisos de lectura. Se validaron únicamente copias temporales de las fuentes de diagramas ya disponibles en memoria; nunca se leyeron archivos de gobierno con herramientas nativas. El JAR alternativo existente recuperó sus permisos originales al finalizar.

No se ejecutaron suites de la capacidad futura, cronómetros, conectores, envíos externos, depuraciones reales, tareas de BLP ni cambios de código. Tampoco se invocaron ready, claim o complete para validar documentos.

## Límites de la verificación del manifiesto

El handler `cycle.synthesize` confirmó escritura de las nueve secciones. La superficie MCP disponible no ofrece una relectura íntegra de ese Markdown: `cortex.read` espera CORTEX y `cortex.format` no conserva el documento Markdown. No se eludió esta limitación leyendo o editando gobierno desde el sistema de archivos.

Heimdall revisó el contenido transmitido de los diez objetivos y su cobertura en las BLPs. No certificó la lectura física completa del manifiesto. Las secciones autorales (1 a 5, 8 y 9) se redactaron por el handler; su persistencia íntegra no se presenta como verificada por relectura.

La inspección del código fuente confirmó dos límites del handler:

- `cycle.create` sustituye metadatos, pero deja el H1 heredado `{name}`; `cycle.synthesize` no tiene superficie para sustituir ese encabezado.
- `cycle.synthesize` llama al reconciliador, que regenera el índice y las métricas de las secciones 6 y 7. No debe afirmarse que esas secciones conservan la prosa enviada.

El título real y la identidad del ciclo figuran en sus metadatos y en el propósito redactado. El residuo cosmético del H1 no representa ausencia de objetivos, pero impide declarar el manifiesto completamente libre de placeholders. Corregir el handler requeriría una autorización de cambio distinta de esta fase de diseño; no se modificó su código.

## Límites funcionales y siguiente decisión

La propuesta no considera Teamwork parte del núcleo. La proyección de BLP-006 incluye contrato agnóstico y adaptador de referencia contra API local simulada; no incorpora ni selecciona un proveedor real. Un conector real y sus credenciales requieren alcance posterior explícito.

Se planifican cuatro handlers opcionales: consulta, revisión, depuración y proyección. No se registraron durante esta fase y no son llamadas rutinarias para anotar tiempos. La captura se integra dentro de acciones existentes autorizadas; si faltan señales o autoridad, informa cobertura limitada sin inventar marcas.

Proyectar no depura. El usuario conserva potestad sobre eliminación incluso de registros no enviados. El diseño reconoce los límites de copias externas o historial de Git no administrados por la capacidad y no promete borrado forense.

La siguiente decisión corresponde al Arquitecto: revisar el diseño y determinar si autoriza una etapa de implementación. Este informe es una constancia de revisión, no un segundo manifiesto ni una autorización implícita.

## Adición revisada: apoyos opcionales de subagentes JARVIS

El Arquitecto añadió la posibilidad de usar subagentes JARVIS para actividades susceptibles de paralelización. Se incorporó a las directrices/reglas del manifiesto y a las secciones 7, 11, 12 y 13 de las seis BLPs. La adición organiza una ejecución futura; no concede permiso de implementación ni cambia estados.

La opción es prescindible. Se mantienen las dependencias entre BLPs y tareas; cada BLP enumera apoyos concretos de análisis o pruebas dentro de una tarea habilitada. Las fuentes, fixtures, salidas, caches y evidencias de ramas concurrentes deben ser disjuntas, con contratos comunes y revisión base definidos. Si no existe capacidad, atribución, autoridad o aislamiento inequívocos, se usa el recorrido secuencial.

La identidad Jarvis existente establece un único claim activo por identidad en todo el workspace. Por eso las instancias adicionales no pueden reclamar otras tareas simultáneamente: solo se admiten apoyos compatibles dentro del mismo encargo, sin claims adicionales. Actividades que requieren tareas reclamadas diferentes se serializan. No se modificaron contratos de identidad, skills, dependencias, AGENTS.md ni plantillas para habilitar una excepción.

Alfred coordina, integra y persiste el gobierno por MCP con procedencia verificable. Los hijos no cambian punteros globales ni sobrescriben memoria de trabajo. Heimdall revisa separado de los autores y conserva solo lectura. La secuencia de cierre quedó precisada tras su revisión: recibir apoyos, integrar, validar/regresión, obtener dictamen cuando lo exija la tarea/compuerta, registrar evidencia, marcar completa por handler autorizado y checkpoint inmediato. Los checkpoints intermedios no declaran finalización.

Las etiquetas de subagente no crean sesiones. Se respeta la SES efectiva y su aislamiento; ramas superpuestas de una misma SES no generan una duración adicional por suma. La delegación no incorpora llamadas rutinarias exclusivas de anotación temporal.

Heimdall releyó mediante MCP las seis BLPs y el párrafo corregido de cierre: adición documentalmente conforme, sin hallazgos materiales abiertos. El dictamen del manifiesto corresponde al contenido transmitido; persiste la limitación de lectura íntegra antes documentada.

Verificación de Alfred: 18 secciones por BLP, 48 AC y 30 tareas sin marcar, seis BLPs draft y cero tareas de implementación creadas. Los 18 bloques conservan la etiqueta plantuml y su fuente; una nueva validación por MCP devolvió 18/18 PASS. No se ejecutó implementación ni se lanzaron subagentes JARVIS de implementación.
