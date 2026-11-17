---
doc_type: guide
status: normative
version: 1.0.0
verified: 2026-11-15
---

<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="./docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>Guía · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Contribuir a ArqUX

Gracias por tu interés. Esta guía te lleva de `git clone` a un PR verde: setup reproducible, tests, convenciones y qué esperar del review.

**Antes de empezar:** para cambios no triviales, abre primero un issue — un PR grande sin discusión previa probablemente se cierre.

## Setup de desarrollo

Requisitos: Python 3.11+ y pip (o [uv](https://docs.astral.sh/uv/) — ver abajo).

```bash
git clone https://github.com/FidelErnesto03/arqux.git
cd arqux
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

El extra `dev` instala: pytest, pytest-asyncio, pytest-cov, ruff, mypy y pre-commit.

**Alternativa con uv:** `uv sync --group dev` usa el grupo `dev` de `[dependency-groups]` (versiones más recientes, sin mypy).

**Nota:** el hook de pre-commit invoca `uv run ruff` — si no tienes uv en PATH, instálalo (`pip install uv`) o ejecuta `ruff check --fix src/ tests/` a mano antes de commitear.

### Verificación

```bash
pytest -q                    # suite completa
pytest tests/e2e -q          # solo end-to-end
ruff check src/ tests/       # linter (mirror de CI)
mypy src/arqux/              # tipos (extra pip dev)
python scripts/check_surfaces.py  # homologación: 115 handlers, versión
```

## Flujo de contribución

1. **Fork** + rama desde `main`: `git checkout -b feat/mi-cambio` (o `fix/`, `docs/`).
2. Commits pequeños con mensajes claros en inglés — el repo usa estilo convencional (`feat:`, `fix:`, `docs:`).
3. `pytest -q`, `ruff check` y `check_surfaces` verdes en local antes de abrir el PR.
4. Abre el PR describiendo el **porqué** del cambio y cómo se verificó.
5. CI corre pytest + ruff (`.github/workflows/ci.yml`).

## Convenciones

- **Código:** inglés; `ruff` formatea y linta (`ruff check --fix` lo aplica el hook).
- **Documentación de usuario:** español nativo en `docs/es/` y archivos de raíz. Identificadores técnicos y código siempre en inglés.
- **Claims:** la documentación se verifica contra el código — no afirmes lo que no puedas ejecutar.
- **Proceso interno:** el equipo núcleo trabaja con ciclos y Blueprints gobernados (`.arqux/`). Como contribuidor externo **no necesitas** ese sistema: issues + PRs normales bastan.

## Tests

- Dónde van: `tests/test_<feature>.py` para unitarios; `tests/e2e/` para flujos completos; `tests/fixtures/` para datos de prueba; `tests/benchmarks/` para rendimiento.
- Markers registrados (`--strict-markers`): `slow` e `integration`. Marca tests lentos con `@pytest.mark.slow`.
- `asyncio_mode = "auto"`: los tests async no necesitan decorador.
- Un test nuevo debe fallar antes del fix y pasar después — es la doctrina del repo.

## Contribuir documentación

- Cada doc lleva front-matter YAML: `doc_type` (`tutorial|guide|reference|explanation|canon|report`), `status` (`normative|informative`), `version`, `verified` (fecha).
- `docs/es/` sigue la taxonomía: `tutorial/`, `guide/`, `reference/` (referencia), `explanation/`, `report/`, `canon/`. Regístralo en `docs/es/README.md`.
- Verifica: `pytest tests/test_frontmatter_consistency.py tests/e2e/test_docs_consistency.py -q`.
- Tablas derivadas del registro (como la de `PERMISSIONS.md`) se **regeneran con su script**, nunca se editan a mano.

## Qué no pedimos

- PRs masivos de formato/renombrado sin issue previo
- Features nuevas sin discusión previa
- Cambios que aflojen verificaciones fail-closed para "hacer pasar" CI
- Versiones o conteos inventados en la documentación

## Review

Un mantenedor revisa el PR; puede pedir cambios o dividir el trabajo. Los PRs se mergean con CI verde. Sin respuesta en un tiempo razonable, un bump amable está bien.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="./docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
