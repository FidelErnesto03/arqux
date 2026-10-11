# ISSUE: import circular en arqux.core.state (bloquea tests)
# Severity: high | Status: verified (fix T-005/G-9 en tree; `import arqux.handlers` OK verificado 2026-09-21; blindaje de regresion en BLP-006) | Handler: heimdall | Date: 2026-07-19

## PROBLEM
Importar `arqux.handlers` (paquete completo) o ejecutar la suite de
tests (`pytest tests/`) falla con ImportError circular:
  arqux.handlers.blueprint._helpers -> arqux.pulse
  -> arqux.state -> arqux.core.state -> arqux.core.state._brain
  -> arqux.core.state (parcial, _cc_parser no disponible)

## WHAT_HAPPENING
Ejecutar `pytest tests/test_task.py` para validar fix de resolucion de ciclo.

## EXPECTED
La suite de tests importa sin circular y corre.

## ACTUAL
ERROR al coleccionar: ImportError: cannot import name '_cc_parser'
from partially initialized module 'arqux.core.state'

## EVIDENCE
arqux/core/state/__init__.py linea 61: `import cortex.core.parser as _cc_parser`
arqux/core/state/_brain.py linea 25: `from . import _HAS_CODEC_CORTEX, _cc_parser`
arqux/pulse.py linea 14: `from .state import ...` (dispara core.state)
arqux/handlers/blueprint/_helpers.py linea 20: `from ...pulse import ...`

## CONTEXT
files: src/arqux/core/state/__init__.py, _brain.py, src/arqux/pulse.py,
       src/arqux/handlers/blueprint/_helpers.py
note: NO afecta a los handlers de task/cycle usados por el MCP server
      (estos importan submodulos especificos sin disparar el circular).

## LESSON
cause:   core.state.__init__ importa cortex.core.parser en nivel superior;
        _brain lo re-importa desde el paquete parcialmente inicializado.
fix:     Mover `import cortex.core.parser` a import diferido (lazy) dentro de
        las funciones que lo usan en _brain.py / __init__.py, o usar
        import relativo consistente sin cruzar el limite de paquete.
prevention: Test de import smoke (`python -c "import arqux.handlers"`) en CI
            para detectar circulares temprano.
