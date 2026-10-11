# ISSUE: writer CORTEX duplica 'text=' al serializar (corrupcion de artifacts)
# Severity: high | Status: verified (E2E re-verificado 2026-09-30 vía dispatch real `arqux call` sobre árbol vigente: artifact T-001.cortex en proyecto scratch con valores CORTEX limpios, 0 duplicaciones text=; evidencia PULSE ARQUX E-0927/E-0928; artifacts históricos saneados por BLP-006 T-1.5) | Handler: jarvis | Date: 2026-07-19

## PROBLEM
Al completar T-004 via MCP server (arqux serve reiniciado), el artifact
T-004.cortex se escribio CORRUPTO: los valores CORTEX aparecen
prefijados con 'text=' o 'text=- text=' repetido
(ej: OBJ:objective{text:"- text=- text=- text=Corregir..."}).

## WHAT_HAPPENING
Completar T-004 (fix session.handoff) tras reinicio del MCP server.

## EXPECTED
El artifact se escribe con valores CORTEX limpios (sin duplicacion).

## ACTUAL
T-004.cortex en disco contenia 'text=text=text=' en OBJ/CNST/CLAIM.
Re-escritura via write_cortex_pair (python uv) REPLICÓ el bug,
confirmando que el writer en la fuente /workspace/ARQUX/src/arqux
está defectuoso (double-encoding de 'text=').

## EVIDENCE
grep T-004.cortex:
  OBJ:objective{text:"- text=- text=- text=Corregir el handler..."
  CNST:pre1{text:"text=text=text=CYCLE-07 abierto..."}
  CLAIM:ac1{criterion:"criterion=criterion=criterion=AC-1..."}

## CONTEXT
files: src/arqux/handlers/task.py (write_cortex_pair), core.state writer
note: task.create (con cycle) FUNCIONA bien; solo el writer corrompe
      al completar/serializar. T-002 completado DESPUES sin corrupcion
      (intermitente — probable cache .pyc del server reiniciado).

## LESSON
cause:   writer aplica escape/encode de 'text=' dos veces al serializar
        entries CORTEX (double-encoding).
fix:     Localizar en write_cortex_pair / _cc_writer el punto donde
        se prefija 'text=' y eliminar la duplicacion.
prevention: Test de round-trip (write -> read -> assert igual) en CI
            para detectar corrupcion de serialization temprano.
