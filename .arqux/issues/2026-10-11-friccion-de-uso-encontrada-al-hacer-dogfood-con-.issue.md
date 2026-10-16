# ISSUE: Friccion de uso encontrada al hacer dogfood con 0.9.0rc3 instalado, reproducible en tres pasos y sin acceso a MCP: (1) `arqux call cycle.synthesize content=...` con la forma `$1:texto` (sin llaves) falla con 'no sections parsed from content', aunque el mensaje no dice cual es la forma correcta. El parser parse_content_sections exige $N:{body}; hay un warning en el log ('P1.2a: found $N: patterns without braces') que no llega a la salida del handler, asi que el usuario solo ve un error opaco. (2) Pasar contenido multilinea por shelldestruye los saltos de linea salvo usando $'...' de bash; `arqux call` no acepta leer el contenido de un archivo ni de stdin, que es la forma natural de enviar un payload CORTEX con 9 secciones. (3) `arqux project` y `arqux cycle` no existen como comandos: hay que usar `arqux call project.init`, `arqux call cycle.create`, y esos handlers exigen `name=DEMO` (no `--name`), lo cual se descubre leyendo el error. No son defectos de correccion sino de ergonomia: el camino funciona y falla cerrado con mensajes utiles cuando el estado es invalido (INVALID_STATE con la lista exacta de placeholders del MANIFEST), lo cual es el comportamiento correcto. Propuesta: que el warning P1.2a aparezca en la salida del handler cuando no se parsea ninguna seccion, aceptar `arqux call handler @archivo` para contenido multilinea, y exponer los handlers project.* y cycle.* como subcomandos de primer nivel. Prioridad baja: el camino via MCP, que es el modo de uso real de los agentes, no sufre nada de esto.
# Severity: low | Status: verified | Handler: alfred | Date: 2026-10-11

## PROBLEM
Friccion de uso encontrada al hacer dogfood con 0.9.0rc3 instalado, reproducible en tres pasos y sin acceso a MCP: (1) `arqux call cycle.synthesize content=...` con la forma `$1:texto` (sin llaves) falla con 'no sections parsed from content', aunque el mensaje no dice cual es la forma correcta. El parser parse_content_sections exige $N:{body}; hay un warning en el log ('P1.2a: found $N: patterns without braces') que no llega a la salida del handler, asi que el usuario solo ve un error opaco. (2) Pasar contenido multilinea por shelldestruye los saltos de linea salvo usando $'...' de bash; `arqux call` no acepta leer el contenido de un archivo ni de stdin, que es la forma natural de enviar un payload CORTEX con 9 secciones. (3) `arqux project` y `arqux cycle` no existen como comandos: hay que usar `arqux call project.init`, `arqux call cycle.create`, y esos handlers exigen `name=DEMO` (no `--name`), lo cual se descubre leyendo el error. No son defectos de correccion sino de ergonomia: el camino funciona y falla cerrado con mensajes utiles cuando el estado es invalido (INVALID_STATE con la lista exacta de placeholders del MANIFEST), lo cual es el comportamiento correcto. Propuesta: que el warning P1.2a aparezca en la salida del handler cuando no se parsea ninguna seccion, aceptar `arqux call handler @archivo` para contenido multilinea, y exponer los handlers project.* y cycle.* como subcomandos de primer nivel. Prioridad baja: el camino via MCP, que es el modo de uso real de los agentes, no sufre nada de esto.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-11T19:51:14Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-16

Confirmado en codigo (SES005): cli.py sigue igual — arqux call acepta solo key=value (sin @archivo ni stdin), no hay subcomandos project/cycle de primer nivel, y el warning P1.2a de parse_content_sections sigue yendo solo al log, no a la salida del handler. Las tres propuestas de ergonomia siguen pendientes. Severidad low correcta: el camino MCP no se ve afectado.

## UPDATE 2026-10-16

Las tres propuestas implementadas: (a) el diagnostico P1.2a ahora viaja en la salida del handler (no_sections_hint en _synthesize_common.py, cableado en cycle.synthesize); (b) arqux call acepta content=@archivo y content=@- para stdin; (c) subcomandos de primer nivel 'arqux project' y 'arqux cycle' que despachan a los handlers project.*/cycle.*. Verificado en vivo con CliRunner y payloads multilinea. Pendiente verified por auditoria.
