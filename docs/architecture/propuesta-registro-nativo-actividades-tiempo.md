# Propuesta: registro nativo de actividades y tiempos en ARQUX

Fecha: 2026-10-14. Estado: diseño ajustado a las siete observaciones y a la precisión posterior de ruta, identidad SES y skill matriz; no implementado.
Idioma: español, establecido por el usuario para esta sesión.

## Base del diseño

ARQUX conserva sus propios registros de actividad en formato de gobierno CORTEX. Cada sesión dentro de un proyecto tiene su propio archivo en <proyecto>/.arqux/timelog/SESXXX_yyyymmdd_hhmiss.cortex, identificado por su entrada SES del brain y la fecha-hora de inicio de esa sesión. Los handlers incorporan fecha-hora de inicio y fin como parte de sus acciones naturales; las duraciones se calculan posteriormente, cuando se necesiten.

Usuario y agente constituyen una unidad funcional de trabajo conjunto. El registro sirve para comprender el avance, conservar continuidad y preparar información utilizable. No se diseña como mecanismo de culpa ni de comparación individual de productividad.

La proyección hacia sistemas externos es adicional e independiente. Exportar no altera la potestad del usuario sobre el registro local ni implica su depuración.

## Correspondencia con las siete observaciones

| Observación | Decisión incorporada |
| --- | --- |
| 1. Solo archivos .cortex, sin nuevas dependencias | Toda persistencia de esta capacidad usa CORTEX y componentes disponibles en ARQUX. No se incorpora base de datos, formato alternativo de registro ni tecnología adicional. |
| 2. Inicio y fin, cálculo asíncrono | El archivo de timelog conserva marcas temporales. No requiere cronómetro, contador acumulativo, servicio de medición ni pulsos periódicos. La duración se deriva bajo demanda. |
| 3. Independencia por sesión y proyecto | Cada sesión tiene <proyecto>/.arqux/timelog/SESXXX_yyyymmdd_hhmiss.cortex, con referencia a su entrada SES del brain y su inicio. No existe un registro global compartido ni mezcla implícita de sesiones. |
| 4. Trabajo conjunto sin culpas | La unidad principal es la actividad conjunta. La distinción humana o agéntica es opcional y requiere relevancia para explicar el avance. |
| 5. Acumulación y potestad del usuario | Los registros permanecen en cada proyecto. Su depuración depende del usuario, sin caducidad ni limpieza automática impuesta. La escritura se integra en handlers naturales. |
| 6. Skill matriz | Las instrucciones se incorporan a la skill matriz existente de ARQUX, sin crear otra skill. Cubren contexto, límites de bloques, cálculo posterior, consulta, incertidumbre y proyección externa. |
| 7. Proyección distinta de depuración | Exportar no borra, compacta, archiva ni mueve el origen. Son acciones separadas. |

Estas decisiones sustituyen las alternativas de almacenamiento y cronometraje de la evaluación inicial. Tampoco queda pendiente elegir entre medir primero al usuario o al agente: rige el trabajo conjunto, con distinción opcional solo cuando sea útil.

## Organización por proyecto y sesión

Ubicación establecida por el Arquitecto, pendiente de implementación:

    <proyecto>/.arqux/timelog/SESXXX_yyyymmdd_hhmiss.cortex

Componentes del nombre:

- SESXXX: identificador de la entrada SES correspondiente en el brain del proyecto. No se genera un identificador paralelo para el timelog.
- yyyymmdd: año, mes y día de inicio de la sesión.
- hhmiss: hora, minuto y segundo de ese mismo inicio; mi corresponde a minutos.

El nombre se deriva de la fecha-hora inicial registrada en la sesión, no de la fecha de una consulta, reanudación, cierre o proyección. La zona horaria debe ser inequívoca y coincidir con la marca de inicio que conserva el archivo. Reanudar la misma sesión conserva su identificador SES, su inicio y su nombre de archivo; una sesión distinta utiliza su propia entrada SES y su propio archivo.

La identidad del registro es la pareja proyecto y referencia SES. El nombre del agente, el BLP activo o una fecha por sí solos no identifican una sesión de forma suficiente. Los metadatos conservan la referencia exacta a la entrada SES del brain y la fecha-hora inicial. Los handlers deben disponer de esa referencia desde la apertura y propagarla internamente; no la inventan a partir de una identidad o de un identificador de conversación ajeno.

Dos sesiones simultáneas del mismo proyecto escriben archivos distintos. La misma tarea puede aparecer en varias sesiones, sin convertir sus bloques en un registro compartido. Cambiar de Alfred a Jarvis dentro de la misma sesión conserva el archivo de esa sesión.

Si una conversación cambia de proyecto, el registro anterior conserva sus límites en el proyecto de origen y el trabajo posterior se registra en el proyecto destino. Antes de escribir, el handler resuelve proyecto y sesión de la ejecución concreta; otra sesión no puede redirigirlo mediante un puntero global.

Una consulta solicitada puede mostrar varios archivos identificando sus procedencias. Esa vista no fusiona ni reescribe registros canónicos. Una proyección de varios registros conserva la relación con cada sesión de origen; no crea un timelog conjunto.

## Contenido del archivo de timelog

El archivo tiene glosario local, metadatos y estructura CORTEX autocontenida. Se reutilizan los componentes vigentes de ARQUX. No constituye un brain paralelo ni se carga íntegramente en la ventana del agente en cada acción.

| Grupo | Contenido |
| --- | --- |
| Identidad | Proyecto, referencia exacta a la entrada SES del brain, fecha-hora inicial de sesión y versión del formato |
| Bloque | Identificador local, actividad y referencias opcionales a ciclo, BLP, tarea o issue |
| Intervalo | Fecha-hora inicio y fin; el fin puede estar pendiente |
| Contexto | Tipo de actividad, resultado o avance y referencia de evidencia cuando exista |
| Estado | Abierto, cerrado o interrumpido; motivo de pausa o interrupción relevante |
| Participación opcional | Humana, agéntica o conjunta, solo si explica mejor el avance |
| Revisión | Corrección explícita, motivo y procedencia |
| Proyección opcional | Destino, bloques y revisiones incluidos, identificador remoto y resultado |

La descripción debe permitir comprender qué se hizo sin copiar conversaciones o BLPs completos. Se utilizan referencias para evitar duplicación.

Son actividades válidas el análisis, diseño, implementación, revisión, soporte y gestión. No se exige crear una tarea artificial para registrar una actividad legítima de sesión.

Los comprobantes de proyección pueden permanecer en una sección diferenciada del mismo archivo de timelog o, si el volumen lo justifica, en un archivo .cortex asociado exclusivamente a esa sesión. Los hechos de actividad y el estado de envío permanecen separados. No se introduce un registro global compartido ni otro formato persistente.

## Registro embebido en acciones naturales

El agente no debe emitir llamadas adicionales solo para anotar marcas, repetir proyecto y sesión, mantener un contador o confirmar cada intervalo. El componente interno de ARQUX resuelve esos datos a partir de la operación y del contexto propio de la ejecución.

Los handlers que ya realizan acciones de gobierno incorporan la actualización correspondiente del timelog. Se reutilizan el lector, escritor y mecanismos de protección disponibles. La integración debe revisar el contrato real y permisos de cada handler: una consulta de lectura no se transforma silenciosamente en escritura y el rol auditor no gana facultades de mutación.

| Acción natural | Efecto propuesto |
| --- | --- |
| Comenzar trabajo en proyecto y sesión | Registrar inicio del bloque dentro de la operación gobernada que materializa ese comienzo |
| Avanzar en una actividad | Actualizar contexto, avance o evidencia cuando corresponda; no abrir un bloque por cada operación interna |
| Cambiar de actividad o contexto relevante | Cerrar el bloque anterior y registrar el comienzo del siguiente con una frontera coherente |
| Pausar, bloquear o ceder trabajo que deja de ejecutarse | Registrar fin del intervalo activo y motivo, sin un contador de espera |
| Retomar una actividad | Crear otro intervalo vinculado a esa actividad |
| Completar, cancelar o cerrar sesión | Registrar fin y resultado del bloque correspondiente |
| Recuperar una interrupción | Conservar el intervalo incompleto y reconciliarlo con evidencia o indicación del usuario |

No se equipara cada llamada MCP con una actividad nueva. No se solicita una interacción periódica ni un pulso de vida solo para mantener el registro.

La skill matriz de ARQUX y la implementación definirán límites concretos: comienzo y finalización de tareas, cambio de actividad o cierre de bloques de análisis. Los handlers aplican esos límites sin delegar al modelo un cálculo continuo.

Cuando el entorno no expone un inicio o fin, se conserva esa limitación. La marca final de una herramienta no demuestra cuándo comenzó todo el trabajo previo. No se inventan intervalos retrospectivos ni se rellena una desconexión desconocida con tiempo activo.

Si el registro falla, se distingue el resultado de la acción gobernada del resultado de su registro temporal. No se repite una acción ya aplicada para reparar una marca; la recuperación utiliza su referencia de operación y evita duplicados.

## Cálculo posterior y asíncrono

La duración de un intervalo cerrado se deriva así:

    duración = fecha-hora fin - fecha-hora inicio

Se conservan marcas con zona horaria inequívoca, preferentemente UTC en almacenamiento, y se presentan en la zona de trabajo del usuario. No se incorpora un reloj de cronometraje separado ni un acumulador en segundo plano.

La consulta puede calcular cada bloque, los intervalos de una actividad dentro de esa sesión y el total de intervalos cerrados. Puede repetirse en cualquier momento sin modificar las marcas originales.

Reglas:

- Un bloque sin fin no se presenta como duración cerrada. Si se muestra un cálculo hasta el momento de consulta, se identifica como provisional.
- Un fin anterior al inicio u otra inconsistencia se señala para revisión; no se corrige inventando datos ni convirtiéndola silenciosamente a cero.
- Una pausa se representa mediante límites de intervalos, sin atribuir actividad al hueco.
- Los intervalos describen lo registrado; no acreditan atención humana o productividad individual no observada.
- Las superposiciones internas de una sesión se interpretan según su relación. Una operación hija no suma otra vez el tiempo que ya contiene el bloque padre.
- No se impone un mínimo de un minuto ni redondeo de facturación al origen. La proyección puede convertir unidades mediante una regla explícita.
- Un total entre sesiones o proyectos se presenta únicamente como vista solicitada, conservando identidad y significado de cada origen. No produce un registro conjunto.

## Unidad funcional usuario-agente

La pregunta principal es qué actividad avanzó, en qué contexto y en qué intervalo. No es quién debe responder por una demora.

Separar tiempos humanos y agénticos requiere utilidad concreta para la actividad. No implica otro registro sistemático, preguntas rutinarias ni inferir dedicación humana a partir de los turnos del agente.

No se suman automáticamente participaciones superpuestas dentro del trabajo conjunto. Cuando distinguirlas sea pertinente, la consulta explica su significado y evita presentarlas como esfuerzo duplicado o culpa de un participante.

## Instrucciones en la skill matriz de ARQUX

El manejo se incorpora a la skill matriz existente de ARQUX. No se crea una skill nueva para el registro nativo. La skill matriz deberá instruir al agente sobre:

La precisión adicional del Arquitecto excluye también crear un nuevo AGENTS.md, otro contrato de agente o nuevas plantillas AGENTS. El AGENTS vigente se utiliza como referencia; las instrucciones de esta capacidad se incorporan a la skill matriz ya existente.

1. Identificar proyecto, entrada SES del brain y actividad sin mezclar ejecuciones concurrentes; resolver el archivo SESXXX_yyyymmdd_hhmiss.cortex con el inicio original de la sesión.
2. Aplicar límites de bloques integrados en handlers existentes.
3. Mantener descripciones breves y referencias suficientes, sin duplicar contexto.
4. Consultar y calcular posteriormente, distinguiendo intervalos cerrados, abiertos e interrumpidos.
5. Interpretar usuario y agente como unidad de trabajo y distinguir participación solo cuando sea relevante.
6. Reconocer fallas de registro y tiempos desconocidos sin fabricar datos ni repetir efectos ya aplicados.
7. Preparar proyecciones externas con relación inequívoca a los registros de origen.
8. Conservar los registros tras proyectarlos y respetar las instrucciones del usuario sobre depuración.

Los handlers realizan la captura rutinaria internamente. Las consultas, revisiones y proyecciones se expondrán mediante las operaciones que determine la implementación; no se exige una nueva batería de llamadas de inicio y parada al agente.

El detalle permanece en los archivos CORTEX del proyecto. La memoria de trabajo contiene solo referencias y resúmenes necesarios. No se impone un pie de cronómetro ni devolver el archivo completo en cada respuesta.

## Proyección externa independiente

La proyección opera sobre registros que ya existen en ARQUX. Puede hacerse posteriormente sin condicionar el origen a un proveedor o conexión externa.

Secuencia:

1. Seleccionar proyecto, sesión y bloques de origen.
2. Calcular intervalos cerrados y preparar descripción y referencias.
3. Resolver destino y reglas particulares: proyecto, tarea, fecha, unidades, redondeo o clasificación.
4. Presentar o ejecutar el envío según la instrucción concreta o política expresamente autorizada por el usuario.
5. Conservar resultado, identificador remoto y relación con bloques y revisiones enviados, en formato CORTEX.

Los payloads que exija una API pueden construirse transitoriamente para el envío; la persistencia propia sigue siendo exclusivamente .cortex. No se agrega tecnología ni dependencia de infraestructura para registrar tiempos.

Cada destino mantiene su estado. Si falla el envío, el origen permanece disponible. Si el resultado es incierto, se reconcilia antes de reintentar. No se promete entrega exactamente una vez si la API no permite acreditarla.

Corregir un bloque proyectado no altera silenciosamente lo enviado. Su revisión permite gestionar después la actualización externa correspondiente.

Exportar, confirmar recepción o cambiar de proveedor no borra, compacta, archiva, mueve ni depura registros locales.

## Acumulación y potestad de depuración

Los registros se acumulan en cada proyecto, separados por sesión. No hay limpieza automática por antigüedad, cierre, volumen o proyección externa.

El usuario tiene plena potestad para conservar, corregir, resumir, archivar o eliminar los registros que indique. Puede depurar tanto datos proyectados como no proyectados. No se impone exportar como condición para borrar ni borrar como consecuencia de exportar.

ARQUX puede mostrar selección y consecuencias y ofrecer respaldo antes de una acción material. Esa información no establece una política de retención ajena al usuario. Una instrucción concreta ya autorizada no debe convertirse en confirmaciones repetitivas.

Archivo o resumen autorizado utiliza también .cortex. Si el usuario dispone eliminación definitiva, se respeta el alcance exacto y se informa la pérdida de reconstrucción o comprobantes, sin conservar copias ocultas contrarias a su decisión.

## Criterios para formalizar la implementación

- Persistencia exclusiva en .cortex y sin nuevas dependencias.
- Un archivo <proyecto>/.arqux/timelog/SESXXX_yyyymmdd_hhmiss.cortex por sesión, con referencia SES real del brain, inicio original y escrituras aisladas.
- Reanudar una sesión conserva su archivo; abrir otra no reutiliza su entrada SES ni mezcla registros.
- Marcas inicio/fin preservadas y cálculo posterior reproducible.
- Registro integrado en handlers naturales, sin llamadas ni tokens adicionales obligatorios para anotación rutinaria.
- Instrucciones incorporadas a la skill matriz existente de ARQUX, sin crear una nueva skill de registro.
- Contexto estable: otra sesión no puede redirigir escrituras con un puntero global.
- Descripciones y participación orientadas al avance del trabajo conjunto.
- Interrupciones y correcciones reconocibles, sin intervalos inventados ni efectos repetidos para reparar el registro.
- Proyección posterior con vínculo al origen y sin depuración implícita.
- Depuración solo por instrucción o política expresamente autorizada por el usuario.
- Pruebas de dos sesiones del mismo proyecto, cambios de proyecto e identidad, pausas, cierre incompleto, reintentos, superposición, envío incierto y eliminación solicitada.

## Estado y límites

Este documento sustituye la propuesta inicial con las decisiones del Arquitecto. La implementación es una capacidad nueva y debe formalizarse separadamente de CYCLE-12/BLP-021, dedicada a fallas de gobernanza.

No se crearon timelogs, modificaron handlers o skills efectivos, activaron cronómetros, migraron registros, proyectaron datos ni depuraron archivos de tiempo. En esta etapa se ajustó el diseño.
