# ROADMAP — ArqUX Framework

**Documento:** `ROADMAP-001`
**Versión:** `0.1`
**Fecha:** `2026-11-14`
**Autor:** Alfred (ejecutor) — mandato: el Arquitecto
**Alcance:** **solo ArqUX Framework.** La Platform (v2.x enterprise) se gobierna en
Proyecto_X y no figura aquí.

**Regla fundacional:** el estado de este documento **no se declara: se verifica.** Cada
fila lleva el comando que la comprueba. Una fila sin comando no entra.

> El roadmap anterior del README (v0.4.x → v2.x) quedaba repartido entre dos vehículos
> sin decirlo. Este documento lo dice: **v0.4.x y v1.x son este framework**; v2.x
> enterprise es la Platform.

---

## 0. Compuerta única

**G1 — Framework v1.0.** No hay fechas. La compuerta es binaria y se abre cuando:

1. Todos los ajustes A verificados **por artefacto** (no por reporte).
2. Suite de corrupción verde.
3. Repo reconciliado (cada cifra pública resuelve a hecho verificado).
4. Caso reproducible multi-actor ejecutado.
5. Paquete de confianza publicado con claims fichados.
6. `xfail` = 0.

**Estado hoy de G1: cerrada.** Ver §2.

---

## 1. Los tres números que definen "primitivo"

| Indicador | Hoy | G1 exige | Comando |
|---|---|---|---|
| Suite | `2708 passed · 2 skipped · 3 xfailed · 0 failed` | 0 failed | `pytest tests/ -q` |
| **Brechas declaradas (`xfail`)** | **3** | **0** | `pytest tests/ -q \| grep -c XFAIL` |
| Ajustes abiertos | 11 | 0 | ver §2 |

Los 2 `skipped` son `faster_whisper` (extra opcional de voz, no defecto).

---

## 2. Tabla de ajustes — estado verificado 2026-11-14

Leyenda: ✅ cerrado · 🟡 parcial · ⬜ abierto · ⛔ roto en release

### 2.1 · Integridad (bloque A-01…A-10)

| ID | Ajuste | Verificación | Estado |
|---|---|---|---|
| A-01 | Escritura quirúrgica y transaccional | `pytest tests/test_cortex_write_transaction.py` (18) + commit `dd096df` | ✅ |
| A-02 | Verificador E/W/I | `grep -rc '"W0' src/arqux/` = 27 · `"E0` = 11 · **`"I0` = 0** | 🟡 **falta I** |
| A-03 | Identidad contextual | `pytest tests/e2e/test_identity_session.py` (25 con las demás) | ✅ |
| A-04 | Paridad schema↔implementación | `arqux call cortex.learn content=...` acepta; `test_blueprint_synthesize_schema_exposes_content` | ✅ |
| A-05 | Matriz de conformidad CORTEX | `pytest tests/test_cortex_conformance.py tests/test_brain_roundtrip_integrity.py tests/test_writer_roundtrip.py tests/test_cortex_two_column_conformance.py tests/test_cortex_invalid_column_conformance.py` (37) | ✅ |
| A-06 | Frontmatter huérfano | `pytest tests/test_frontmatter_consistency.py tests/e2e/test_integrity_gates.py` (32) | ✅ |
| A-07 | Transporte MCP | `src/arqux/server.py:250-262` + `pytest tests/e2e/test_transport_cli.py` | ✅ |
| A-08 | `issue_create(handler=)` | `arqux call issue.create ... handler=Alfred` → `ok` | ✅ |
| A-09 | Regresión de corrupción | `pytest tests/e2e/test_integrity_gates.py` | ✅ |
| A-10 | `cortex_verify` canónico | `arqux cortex-verify <brain>` → `OK` | ✅ |

**Resultado: 9 de 10 cerrados.** El `0.9.0-report.md` afirmaba "A-02 pendiente;
A-03…A-10 sin verificar". La realidad medida es 9/10. *El reporte no midió el artefacto.*

### 2.2 · Verdad del repo (bloque A-11…A-13)

| ID | Ajuste | Verificación | Estado |
|---|---|---|---|
| A-11 | Toda cifra del README resuelve a hecho | `arqux handlers \| wc -l` = **111**; `ARCHITECTURE.md` dice **73** (5 lugares); `SECURITY.md` soporta **0.4.x** y la vigente es **0.9.0** | ⛔ **roto** |
| A-12 | Flags de release coherentes | `gh release view` → `prerelease: false`; README dice `status-beta` | ⛔ **roto** |
| A-13 | Quickstart reproducible en CI | Verificado **a mano** hoy (venv limpio + init OK); **no hay job** | ⬜ |

### 2.3 · Deuda de diseño (bloque A-14…A-21)

| ID | Ajuste | Estado | Nota |
|---|---|---|---|
| A-14 | Arquitectura de directrices locales | ⬜ | Requiere diseño nuevo |
| A-15 | Pipeline de aprendizaje completo | ⬜ | **Bloqueado por A-22** |
| A-16 | Escalera NANO operativa | ⬜ | Depende de A-15 |
| A-17 | Caso reproducible multi-actor | ⬜ | Requiere ≥2 harness reales |
| A-18 | Paquete de confianza | ⬜ | Depende de A-11 |
| A-19 | Validación de nicho y piloto | ⬜ | Fuera del código |
| A-20 | Nombre y marcas (TM 9/42/35) | ⬜ | Fuera del código |
| A-21 | Portal congelado | ✅ | Cumplido: solo cambios de verdad |

### 2.4 · Ajuste nuevo — A-22 (decisión del Arquitecto, 2026-11-14)

| ID | Ajuste | Verificación | Estado |
|---|---|---|---|
| **A-22** | **Absorber el motor de aprendizaje como componente nativo de ARQUX** | `arqux call cortex.learn` en venv **sin codec** → debe funcionar | ⛔ **roto hoy** |

**Evidencia del defecto, medida:**

| Instalación | `cortex.verify` | `cortex.learn` |
|---|---|---|
| Sin `[codec]` | ❌ MISSING_DEPENDENCY | ❌ ENGINE_UNAVAILABLE |
| Con `[codec]` → codec **0.6.2** | ✅ | ✅ |
| Con codec **1.0.0** (el certificado) | ❌ | ❌ |

**Causa raíz:** `codec-cortex 1.0.0` eliminó el módulo `learning` (verificado: no existe en el
paquete). ARQUX depende de `cortex.learning.{candidates,elevation,errors,index,policy}` desde
`src/arqux/core/learning/_common.py:17-21`.

**Principio rector (ratificado por el Arquitecto):** *CODEC-CORTEX es un protocolo de
almacenamiento y convención de memoria; el aprendizaje pertenece al manejo que ARQUX hace de
su brain.* El código ya lo declaraba a medias — `src/arqux/cortex/reader.py:3-4`:
> *"ARQUX's own parser is the single authority (CODEC-CORTEX is a format convention, not an
> implementation — T-028)."*

Se absorbió la lectura, no la estructura ni el aprendizaje. A-22 cierra esa asimetría.

**Alcance de la portación:**

| Módulo CLE | LOC | Destino |
|---|---|---|
| `policy.py` | 520 | `src/arqux/core/learning/` |
| `elevation.py` | 454 | idem |
| `workspace.py` | 388 | idem |
| `scoring.py` | 355 | idem |
| `index.py` | 322 | idem |
| `conditions.py` | 285 | idem |
| `candidates.py` | 214 | idem |
| `errors.py` | 58 | idem |
| **Total** | **~2.596** | + modelo de documento propio |

**Dato que abarata el trabajo:** el CLE **no tiene dependencias externas** — solo stdlib
(`json`, `hashlib`, `math`, `re`, `dataclasses`, `uuid`). Su único acoplamiento es el modelo
AST del codec, que ARQUX puede absorber.

**Licencia:** el codec es **MPL-2.0**; ARQUX es **Apache-2.0**. Si se porta código derivado,
esos archivos quedan MPL-2.0 y deben declararlo. Si se reimplementa la lógica, queda Apache
limpio. **Decisión pendiente del Arquitecto.**

**BLP:** `BLP-025` (CYCLE-15, draft).

---

## 3. Brechas declaradas — los 3 `xfail`

Son la definición operativa de "primitivo": el producto **admite por escrito** lo que no sabe
hacer. G1 exige 0.

| Gap | Capacidad ausente | Test | Nota |
|---|---|---|---|
| 2.6 | Consulta transversal por corpus | `test_cross_corpus_query_exists` | La hereda la Platform (B-05) |
| 2.9 | Migración que repara contenido | `test_migration_reports_content_repairs` | Reutiliza `reader.py` + `transaction.py` de A-01 |
| 2.12/U4 | Helper público de emisión ideática | `test_public_emit_helper_is_exported` | Helper sobre el writer existente |

---

## 4. Generación de BLPs

El roadmap **es la fuente** de los blueprints. Ningún BLP nace sin fila aquí.

| Fila del roadmap | BLP | Ciclo | Estado | Objetivo |
|---|---|---|---|---|
| **A-22** · Absorber CLE | **BLP-025** | CYCLE-15 | draft | Learning nativo, sin dependencia de `cortex.learning` |
| Codec 1.0 (parse/validate/render/select) | BLP-021 | CYCLE-15 | draft | Adopción de la superficie plana v1.0 — **hermano de A-22**, comparte el principio |
| Gap 2.6 · corpus query | *por crear* | — | — | Consulta transversal |
| Gap 2.9 · migración que repara | *por crear* | — | — | `plan_repairs` |
| Gap 2.12/U4 · emisión ideática | *por crear* | — | — | `emit_ideatic` público |
| A-02 · nivel I | *por crear* | — | — | Familia de diagnósticos informativos |
| A-11 · verdad del repo | *por crear* | — | — | Reconciliar ARCHITECTURE/SECURITY/README |
| A-12 · flags de release | *por crear* | — | — | `prerelease` coherente con madurez |
| A-13 · quickstart CI | *por crear* | — | — | Job que instala desde PyPI y valida árbol |
| A-14 · directrices locales | *por crear* | — | — | Versionado, adaptadores, reversión |
| A-15 · pipeline de aprendizaje | *por crear* | — | — | **Depende de BLP-025** |
| A-17 · caso multi-actor | *por crear* | — | — | ≥2 agentes, ≥2 harness |
| A-18 · paquete de confianza | *por crear* | — | — | Publicable sin claims sin ficha |

**Regla de precedencia:** BLP-025 (A-22) va antes que A-15 y antes que BLP-021. Sin learning
nativo, la adopción de codec 1.0 deja `cortex.learn` muerto y A-15 no tiene base.

---

## 5. Ruta crítica

```
A-22 / BLP-025 (learning nativo)
    │
    ├──► A-02 (nivel I) ──► A-15 (pipeline) ──► A-16 (escalera NANO)
    │
    ├──► BLP-021 (codec 1.0)  ← deja de ser crítico: solo parse/render
    │
    └──► gaps 2.6 / 2.9 / 2.12  →  xfail = 0

A-11 (repo) ──► A-12 (flags) ──► A-13 (CI) ──► A-18 (confianza) ──► G1

A-14 (directrices) ──► A-17 (multi-actor) ──────────────────────┘
```

**Primer movimiento:** A-22 / BLP-025. Es el que desbloquea el aprendizaje, alinea el
principio de propiedad con el código, y elimina el riesgo de que cualquier actualización del
codec apague `cortex.learn`.

---

## 6. Fuera de alcance de v1.0

Para que 1.0 no crezca hasta ser inalcanzable:

- Coordinación multiusuario en tiempo real o sync automático (es Platform: B-01…B-08).
- Certificación, cumplimiento normativo o "auditoría independiente".
- Interfaz visual de gobernanza (es v2.x / Platform).
- Marketplace de skills.
- Dashboard multiproyecto.
- Cualquier capacidad de la Platform.

---

## 7. Cómo se mantiene vivo

`scripts/gate_status.py` recorre §2 y §3, ejecuta cada verificación y emite
`PASS`/`PARTIAL`/`FAIL` por fila, más el veredicto de G1.

Este documento publica **la salida del script**, no la memoria de nadie. Si el script no
puede verificar una fila, la fila se marca `UNVERIFIED` — nunca se asume verde.

---

*Escrito el 2026-11-14 tras auditoría por artefacto de A-01…A-10. La tabla se actualiza con
evidencia; no se reinterpreta.*
