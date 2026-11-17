---
doc_type: canon
status: normative
version: 1.0.0
verified: 2026-11-16
---

<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="../../docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>Canon · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Formato documental ArqUX — presentación oficial de la documentación

Especificación normativa de la superficie visual de los documentos públicos. Fuente de identidad: **ArqUX Brand Kit v1.0** (`Proyecto_X/docs/brand-kit-v1/`). Los bloques de marca son **generados**, no manuscritos — se aplican con `scripts/format_docs.py` y los verifica `tests/e2e/test_docs_contract.py`.

## 1. La pieza de marca

Todo documento público abre con el bloque `DOC-BRAND` tras su front-matter:

```html
<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="{REL}docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="{REL}docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>{doc_type_es} · {status_es} · ArqUX {version}</sub></p>
<!-- /DOC-BRAND -->
```

- `{REL}` = prefijo relativo desde el doc hasta la raíz (`./` en raíz, `../../../` en `docs/es/guias/`). Las rutas son **relativas** — el corpus se lee en GitHub, en local y en cualquier mirror sin tocar una URL.
- `<picture>` resuelve light/dark por `prefers-color-scheme` — la regla del kit "logo claro sobre superficie clara, oscuro sobre oscura" se cumple en ambos temas de GitHub.
- El ribbon `<sub>` traduce el front-matter: `doc_type` y `status` en español, `version` literal. Solo aparece si el doc tiene front-matter.
- `width="240"` fijo — el lockup no baja del tamaño probado de legibilidad (regla del kit).

## 2. El pie

Todo documento cierra con `DOC-FOOT`:

```html
<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX {version} · verificado {verified} · <a href="{REL}docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
```

El pie responde tres preguntas al lector sin scroll: qué versión describe, cuándo se verificó, y dónde está el mapa del corpus.

## 3. Tipografía y color (capa de tokens)

Markdown se renderiza con la tipografía del host (GitHub); la pila de marca queda reservada para superficies controladas (portal, VS Code, HTML generado): **IBM Plex Sans/Inter** para interfaz, **IBM Plex Mono/JetBrains Mono** para material técnico — `tokens/arqux-colors.css` del kit es la referencia.

Roles de color al escribir gráficos o HTML inline en docs:

| Token | Rol en docs |
|---|---|
| `ink-950 #0A1420` | Texto/estructura |
| `amber-700 #D77A00` | Ruta de marca, acción — **nunca** texto pequeño sobre fondo claro |
| `teal-400 #61D9C6` | Conexiones de contexto compartido — uso sparing |
| success/warning/error | Estados semánticos, nunca decoración |

El color nunca porta estado solo — mismo principio del kit (WCAG 2.2 AA).

## 4. Reglas de uso del logotipo (del kit, aplicadas a docs)

- Usar los SVG del kit (vendored en `docs/assets/brand/`) — no reconstruir la marca con texto ni aproximar geometría.
- Sin glow/gradiente/outline/rotación/recorte extra — el master ya trae su efecto.
- Sin tagline adosado al logo — el ribbon `<sub>` es el único acompañamiento permitido y proviene del front-matter.
- Símbolo standalone (`arqux-symbol.svg`) para favicon/avatar/icono; lockup completo para cabeceras.

## 5. Uniformidad estructural por `doc_type`

| doc_type | Esqueleto canónico |
|---|---|
| `tutorial` | título → objetivo/tiempo → prerequisitos → pasos con comandos reales → "siguiente" |
| `guide` | título → propósito-actor → procedimiento verificado → ver también |
| `reference` | título → tabla(s) de consulta generadas o verificadas → regeneración si aplica |
| `explanation` | título → pregunta que responde → razonamiento → límites honestos |
| `canon` | título → norma literal → ejemplos `.cortex` literales → excepciones |
| `report` | título → datos medidos → alcance del dato → fecha |

Regla de oro ya vigente: **el contenido se verifica o se marca** — la marca es presentación, nunca sustituto de evidencia ("Product truth" del kit: la identidad no fabrica claims).

## 6. Excepciones declaradas

Sin bloque de marca (justificación en `scripts/format_docs.py` `NO_BRAND`):

- `AGENTS*.md` — kernels de gobernanza, no documentación de usuario
- `CHANGELOG.md` — formato keep-a-changelog propio
- `PILOT_MODE.md` — stub retirado
- `llms.txt` — índice de máquina (formato llmstxt.org)
- `docs/es/especificacion/secciones-cerebro-canon.md` — shard canónico sin front-matter
- `HANDLERS.md` — recibe la marca **desde su generador** (`generate_handlers_md.py`), no del script — la regeneración no la borra

## 7. Operación

```bash
python scripts/format_docs.py           # aplica/repara cabecera+pie en todo el corpus
python scripts/format_docs.py --check   # verifica presencia (lo corre el gate)
```

Idempotente por marcadores `DOC-BRAND`/`DOC-FOOT`: re-ejecutar reemplaza los bloques sin tocar el contenido. Doc nuevo → `format_docs.py` tras su front-matter.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-16 · <a href="../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
