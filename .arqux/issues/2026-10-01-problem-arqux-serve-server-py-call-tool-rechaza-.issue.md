# ISSUE: PROBLEM: arqux serve (server.py call_tool) rechaza tool names con prefijo de servidor (ej. arqux_project_status) y la rama NOT_FOUND construye TextContent(text=CortexOUT(...)) sin .to_text() — el cliente recibe un error Pydantic ilegible en vez del mensaje real. EVIDENCE: 2026-10-01 — todas las llamadas arqux_* fallaron con 'Input should be a valid string [input_value=CortexOUT(profile=OUT-ER...)'. Reproduccion: call_tool('arqux_project_status') → NOT_FOUND CortexOUT; call_tool('project_status') → OK. FIX APLICADO (sin commitear en el momento del reporte, src/arqux/server.py + espejo site-packages): call_tool normaliza el nombre removiendo prefijo {PRODUCT_NAME}_/{PRODUCT_NAME}. antes del lookup; NOT_FOUND usa .to_text(). MCP funcional post-respawn. PENDIENTE: test de regresion (nombre prefijado + nombre inexistente). Defecto distinto a E-1032: capa de transporte, no de contenido.
# Severity: high | Status: verified | Handler: alfred | Date: 2026-10-01

## PROBLEM
PROBLEM: arqux serve (server.py call_tool) rechaza tool names con prefijo de servidor (ej. arqux_project_status) y la rama NOT_FOUND construye TextContent(text=CortexOUT(...)) sin .to_text() — el cliente recibe un error Pydantic ilegible en vez del mensaje real. EVIDENCE: 2026-10-01 — todas las llamadas arqux_* fallaron con 'Input should be a valid string [input_value=CortexOUT(profile=OUT-ER...)'. Reproduccion: call_tool('arqux_project_status') → NOT_FOUND CortexOUT; call_tool('project_status') → OK. FIX APLICADO (sin commitear en el momento del reporte, src/arqux/server.py + espejo site-packages): call_tool normaliza el nombre removiendo prefijo {PRODUCT_NAME}_/{PRODUCT_NAME}. antes del lookup; NOT_FOUND usa .to_text(). MCP funcional post-respawn. PENDIENTE: test de regresion (nombre prefijado + nombre inexistente). Defecto distinto a E-1032: capa de transporte, no de contenido.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-01T23:18:13Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage

## UPDATE 2026-10-02

FIX validado + test de regresion agregado (issue 1, cerrada como fixed). CAUSE: call_tool en src/arqux/server.py registraba handlers solo bajo el nombre safe (dotted->underscore) y la rama NOT_FOUND construia TextContent(text=CortexOUT(...)) sin .to_text() -> error Pydantic ilegible en el cliente. FIX (ya aplicado en la sesion del 2026-10-01, ahora con candado de regresion): normalizacion removeprefix(f"{PRODUCT_NAME}_") / (f"{PRODUCT_NAME}.") antes del lookup + .to_text() en NOT_FOUND. FIX TEST: nuevo tests/test_server_call_tool.py con 3 casos — (1) nombre prefijado arqux_test_echo resuelve, (2) nombre plain no afectado, (3) NOT_FOUND retorna texto legible con OUT_ERROR/NOT_FOUND y sin dump de Pydantic (extrae request_handlers[CallToolRequest], unwrap ServerResult.content). Verificado ademas que el venv de ARQUX resuelve arqux desde src (instalacion editable): sin drift entre espejo site-packages y fuente. Suite ARQUX: 1851 passed, 14 skipped (pre-existentes CI). PREVENTION: toda ruta de error de transporte debe serializar CortexOUT via .to_text() y cubrirse con test de contrato a nivel handler.
