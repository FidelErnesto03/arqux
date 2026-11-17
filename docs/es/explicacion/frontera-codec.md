---
doc_type: explanation
status: informative
version: 1.0.0
verified: 2026-11-15
---

<!-- DOC-BRAND -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../../../docs/assets/brand/arqux-logo-primary-dark.svg">
    <img alt="ArqUX" src="../../../docs/assets/brand/arqux-logo-primary-light.svg" width="240">
  </picture>
</p>
<p align="center"><sub>Explicación · Informativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Frontera del codec — codec-cortex 1.0.x

> ES es la fuente canónica; el espejo EN vive en `docs/en/explicacion/frontera-codec.md`. En divergencia, gana este documento.

El codec es una **convención de formato**, no el dueño de la semántica de gobierno.

## Lo que ArqUX consume de `codec-cortex>=1.0,<1.1`

| Capacidad | Superficie del codec | Adaptador ArqUX |
|---|---|---|
| Parse estricto 1.0 | `codec_cortex.dispatcher.parse_cortex` | `model.from_codec_v1` → `arqux.cortex.model` |
| Canonicalización / hashing | `canonicalize` (vía `_bind_v1_api`, aún sin consumidor vivo), `hash_cortex` | binding v1 en `core/state`; `hash_cortex` es `arqux.security` nativo |
| Compilación HCORTEX (lado escritura) | `compile_hcortex` | frontera de render en `core/state` |

## Lo que ArqUX NO consume (nativo, propio)

| Capacidad | Dueño | Notas |
|---|---|---|
| Motor de aprendizaje | `core/learning/` | el codec eliminó `learning` en 1.0 — totalmente nativo desde BLP-002/003/004; `grep -rInE "cortex\.learning\|codec_cortex\.learning" src/arqux/` debe permanecer vacío |
| Validación de gobierno (E0xx) | `cortex/level_policy.py` | política portada sobre el modelo nativo; equivalencia vs legacy verificada en el corpus de fixtures |
| Selectores `$N/SIGIL:name` | `cortex/selectors.py` | consumidos por la capa CRUD |
| Lectura HCORTEX | `cortex/read_renderer.py` | renderer portado sobre el modelo nativo |
| Writer | `cortex/writer.py` | emite el dialecto 1.0 incondicionalmente: `$0:format{cortex:1.0, encoding:UTF-8}` + declaraciones ejecutables (I001/G010/G022/G025), contratos `open:true` |
| Mutación del brain | `core/state/_crud.py` | leer → mutar → re-serializar → **re-parse estricto** → validar → escritura atómica; una serialización que no re-parsea aborta (axioma silent_corruption) |

## Explícitamente fuera de alcance

- `slots`, `migrate`, módulos harness del codec — sin uso en ArqUX.
- Sigilo legacy `GSIG:` — promovido a declaraciones ejecutables al escribir; nunca emitido.
- Pseudo-sección legacy `$0.1` — normalizada a `$19` al escribir.

## Política de sincronía (cuando CODEC-CORTEX evoluciona)

1. El pin es `>=1.0,<1.1`: bumps minor se adoptan al publicarse; líneas major requieren nuevo Blueprint.
2. Ante un upgrade del codec: correr `test_cortex_v1_conformance.py` en venv limpio — re-verifica la equivalencia parse/validate/render contra el baseline legacy.
3. Si el codec añade una capacidad que ArqUX ya posee (validate, selectors, render-read), ArqUX conserva su implementación — la semántica de gobierno no se externaliza.
4. Una regresión del codec que rompa `can_parse` es expuesta por `codec_cortex_diagnostics()` — nunca degradada en silencio.

## Modelo de entorno

| Entorno | Binding | Rol |
|---|---|---|
| `codec-cortex 1.0.x` instalado | `api='v1'` | **Canónico** — el pin; la suite debe mantener delta 0 |
| Solo `cortex` 0.6.x legacy | `api='legacy'` | Degradado pero funcional (parser tolerante) |
| Sin codec | `available=False` | El reader/writer nativo de ArqUX sigue operando; las rutas dependientes del codec reportan, no crashean |

**Por qué existe la frontera:** el formato `.cortex` es propiedad del codec; la *gobernanza* (qué secciones, qué sigils, qué invariantes) es propiedad de ArqUX. La frontera fail-closed garantiza que una escritura nunca pase sin validar — y que ArqUX pueda operar degradado si el codec no está.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
