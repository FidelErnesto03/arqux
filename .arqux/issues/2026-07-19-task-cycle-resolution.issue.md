# ISSUE: task.create / task.read — resolucion de ciclo incorrecta
# Severity: high | Status: verified (remanente cerrado por BLP-006 2026-09-21: _resolve_task_file con cascada ciclo-path > ciclo actual > single-match > TASK_AMBIGUOUS; 6 tests regresion + repro live T-004 en 3 ciclos; suite 1355 pass) | Handler: heimdall | Date: 2026-07-19

## PROBLEM
task.create ignora el ciclo solicitado y coloca la tarea en el ultimo ciclo
abierto por orden alfabetico; task.read ignora el path de ciclo y devuelve la
primera coincidencia de task_id entre TODOS los ciclos. Resulta en colision
de IDs de tarea (T-001 existe en CYCLE-02/03/07/08) y tareas no
localizables por ciclo.

## WHAT_HAPPENING
Crear T-001 para Jarvis en CYCLE-07 y BLP-001 en CYCLE-08 via handlers MCP.

## EXPECTED
task.create debe respetar el ciclo pasado (o el actual del proyecto) y
task.read debe resolver usando el ciclo del path proporcionado.

## ACTUAL
task.create escribio T-001 en CYCLE-08 (open_cycles[-1]) aunque se paso
path=ARQUX sin ciclo; task.read con path=.../CYCLE-08 devolvio el T-001 de CYCLE-07.

## EVIDENCE
arqux/handlers/task.py linea 94-96:
  open_cycles = [p.name for p in sorted(cycles_base.iterdir()) if p.is_dir()]
  cycle_id = open_cycles[-1]
_load_task itera ciclos y devuelve primera coincidencia ignorando path de ciclo.

## CONTEXT
cycle: CYCLE-07/CYCLE-08 | blp: BLP-001 | handler: task.create, task.read
task: T-001 | files: src/arqux/handlers/task.py

## LESSON
cause: create_task no acepta parametro de ciclo y usa open_cycles[-1];
       _load_task no filtra por ciclo del path.
fix:   Agregar parametro cycle opcional a task_create; si se pasa, usarlo;
       si no, usar current_cycle(). En _load_task, restringir busqueda al
       ciclo derivado del path (o del parametro cycle) antes de buscar por task_id.
prevention: Test de regresion que cree una tarea en un ciclo especifico y la
       lea con path de ese ciclo, verificando que no colisiona con otro ciclo.
