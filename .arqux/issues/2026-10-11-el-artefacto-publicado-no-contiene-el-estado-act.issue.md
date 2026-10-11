# ISSUE: El artefacto publicado no contiene el estado actual del repositorio. El tag v0.9.0rc1 (annotated 70a25e7) peel-a al commit e0dc8e8, mientras HEAD es c119019: cuatro commits posteriores NO estan en la release. git diff --stat v0.9.0rc1..HEAD muestra 10 archivos, +203/-18: scripts/check_surfaces.py (+133, la homologacion de superficies no existe en el tag), .pre-commit-config.yaml (+6, el hook que la invoca), docs/release/benchmark-0.9.0.json (12 lineas, benchmark refrescado), docs/release/0.9.0-report.md (8 lineas, informe actualizado), mas CHANGELOG.md, HANDLERS.md, README.md, src/arqux/skills/comms.skill.md y tests/benchmarks/test_memory_benchmark.py. Impacto: quien instale 0.9.0rc1 desde PyPI o clonee el tag obtiene un arbol sin la tooling de homologacion y con el informe de release describiendo un estado que el tag no tiene. Verificado en PyPI: 0.9.0rc1 esta publicado pero 'latest' resuelve a 0.8.2 (correcto para una pre-release, pero significa que pip install arqux NO da 0.9.0rc1). Fix: reetiquetar una vez el gate pase, o republicar el informe declarando explicitamente que describe HEAD y no el tag.
# Severity: high | Status: open | Handler: alfred | Date: 2026-10-11

## PROBLEM
El artefacto publicado no contiene el estado actual del repositorio. El tag v0.9.0rc1 (annotated 70a25e7) peel-a al commit e0dc8e8, mientras HEAD es c119019: cuatro commits posteriores NO estan en la release. git diff --stat v0.9.0rc1..HEAD muestra 10 archivos, +203/-18: scripts/check_surfaces.py (+133, la homologacion de superficies no existe en el tag), .pre-commit-config.yaml (+6, el hook que la invoca), docs/release/benchmark-0.9.0.json (12 lineas, benchmark refrescado), docs/release/0.9.0-report.md (8 lineas, informe actualizado), mas CHANGELOG.md, HANDLERS.md, README.md, src/arqux/skills/comms.skill.md y tests/benchmarks/test_memory_benchmark.py. Impacto: quien instale 0.9.0rc1 desde PyPI o clonee el tag obtiene un arbol sin la tooling de homologacion y con el informe de release describiendo un estado que el tag no tiene. Verificado en PyPI: 0.9.0rc1 esta publicado pero 'latest' resuelve a 0.8.2 (correcto para una pre-release, pero significa que pip install arqux NO da 0.9.0rc1). Fix: reetiquetar una vez el gate pase, o republicar el informe declarando explicitamente que describe HEAD y no el tag.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-11T17:59:10Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage
