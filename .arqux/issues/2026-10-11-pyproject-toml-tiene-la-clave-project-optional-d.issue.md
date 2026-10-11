# ISSUE: pyproject.toml tiene la clave [project.optional-dependencies].dev declarada DOS veces: linea 64 (pytest>=7.0.0, pytest-asyncio>=0.21.0, pytest-cov>=4.0.0, ruff>=0.4.0, mypy>=1.5.0, pre-commit>=3.0.0) y linea 131 (pytest>=9.1.1, pytest-asyncio>=1.4.0, pytest-cov>=7.1.0, ruff>=0.15.20, pre-commit>=4.0.0, sin mypy). Es TOML invalido por clave duplicada. Efecto actual: el wheel construido en dist/ resuelve el PRIMER bloque (verificado: el METADATA incluye mypy>=1.5.0), por lo que mypy si se instala; el segundo bloque es codigo muerto. Riesgo: la resolucion de claves duplicadas no es uniforme entre parsers (tomllib de Python 3.11.8 devuelve el primero; otros pueden devolver el ultimo), y si el bloque efectivo fuera el segundo, mypy desapareceria SIN QUE NADIE LO NOTARA, porque el paso 'Type-check with mypy' de CI.yml esta envuelto en '|| true' Y tiene continue-on-error: true. Seria un type-check que nunca corre y nunca falla. Fix: eliminar el bloque duplicado y decidir explicitamente si mypy permanece; si permanece, quitar el || true para que su ausencia sea visible.
# Severity: medium | Status: open | Handler: alfred | Date: 2026-10-11

## PROBLEM
pyproject.toml tiene la clave [project.optional-dependencies].dev declarada DOS veces: linea 64 (pytest>=7.0.0, pytest-asyncio>=0.21.0, pytest-cov>=4.0.0, ruff>=0.4.0, mypy>=1.5.0, pre-commit>=3.0.0) y linea 131 (pytest>=9.1.1, pytest-asyncio>=1.4.0, pytest-cov>=7.1.0, ruff>=0.15.20, pre-commit>=4.0.0, sin mypy). Es TOML invalido por clave duplicada. Efecto actual: el wheel construido en dist/ resuelve el PRIMER bloque (verificado: el METADATA incluye mypy>=1.5.0), por lo que mypy si se instala; el segundo bloque es codigo muerto. Riesgo: la resolucion de claves duplicadas no es uniforme entre parsers (tomllib de Python 3.11.8 devuelve el primero; otros pueden devolver el ultimo), y si el bloque efectivo fuera el segundo, mypy desapareceria SIN QUE NADIE LO NOTARA, porque el paso 'Type-check with mypy' de CI.yml esta envuelto en '|| true' Y tiene continue-on-error: true. Seria un type-check que nunca corre y nunca falla. Fix: eliminar el bloque duplicado y decidir explicitamente si mypy permanece; si permanece, quitar el || true para que su ausencia sea visible.

## CONTEXT
reported_by: alfred
reported_at: 2026-10-11T17:59:11Z

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage
