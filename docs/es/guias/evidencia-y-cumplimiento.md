---
doc_type: guide
status: normative
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
<p align="center"><sub>Guía · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Evidencia y cumplimiento — guía para CISO

Guía operativa para oficial de cumplimiento o auditor externo. Recorre el ciclo completo de la evidencia firmada: generar un bundle sin que salga material privado, firmarlo con Ed25519, y verificarlo en terreno propio sin acceso al workspace ni al repositorio. Cada afirmación termina en un comando ejecutable — si no puede ejecutarse, no se afirma.

## Para quién es

Para el evaluador que debe decidir si la evidencia que produce ArqUX es admisible en su marco de control. No requiere confianza en el proveedor: la verificación corre en el terreno del auditor, con material mínimo (el bundle + una clave pública).

## El contrato de evidencia

**Qué sale del workspace** (`arqux evidence export`):

| Contenido | Origen | Forma |
|---|---|---|
| Spans de sesión | `.arqux/timelog/SES*.cortex` | `SPN:` — sesión, identidad del agente, apertura/cierre, SHA-256 del timelog fuente |
| Eventos de gobierno | sección `$5` de cada timelog, sigilos `AUD`/`DEC`/`ERR`/`LOOP` | líneas verbatim |

**Qué nunca sale**: transcripciones de chat, prompts, código fuente del proyecto, y toda entrada marcada `visibility:"private"` — salvo decisión humana explícita (`--allow-raw`). El gate es *fail-closed*: ante material privado y ausencia de flag, el export se bloquea.

## Procedimiento 1 — Llaves y firma

```bash
# Generar par Ed25519 (seed privado + público, archivo 0600)
arqux policy keygen .arqux/keys/emisor.key
# → key_id:8f3a…  created .arqux/keys/emisor.key

# Firmar un documento — anexa la línea SIG:signature al propio archivo
arqux policy sign bundle.cortex --key .arqux/keys/emisor.key
# → signed bundle.cortex key_id:8f3a… payload_sha256:818b…

# Verificar
arqux policy verify bundle.cortex --key .arqux/keys/emisor.key
# → SIGNATURE_VALID key_id:8f3a…   (exit 0)
```

La firma cubre los **bytes canónicos** del documento (todo excepto las líneas `SIG:`). Ed25519 es implementación propia (RFC 8032, `signing.py`) — sin dependencia criptográfica externa.

## Procedimiento 2 — Export con los tres modos

Timelog de demostración: una sesión con tres eventos, uno marcado `visibility:"private"`.

```bash
# Modo por defecto: gate fail-closed
arqux evidence export --out bundle.cortex
# → EXPORT_BLOCKED: 1 private-marked field(s) found — export blocked.
#   Pass --redact-private to strip them or --allow-raw to include.   (exit 1)

# Modo redacción: lo privado se excluye y el conteo queda registrado
arqux evidence export --out bundle.cortex --redact-private
# → bundle bundle.cortex spans=1 events=2 redacted=1

# Modo auditoría: lo privado sale verbatim — decisión humana explícita
arqux evidence export --out bundle-raw.cortex --allow-raw
# → bundle bundle-raw.cortex spans=1 events=3 redacted=0
```

Los flags son mutuamente excluyentes. El bundle resultante declara su propio estado en `EVD:bundle{… redacted:1, raw:false}` — el auditor sabe qué modo se usó sin preguntar.

## Procedimiento 3 — Verificación externa, sin el workspace

El emisor entrega al auditor **dos artefactos**: el bundle firmado y un archivo de clave pública. La clave privada (`seed:`) nunca sale.

```bash
# Lado del EMISOR — publicar solo la línea public: del keypair
grep '^public:' .arqux/keys/emisor.key > emisor.pub

# Lado del AUDITOR — directorio vacío, sin repo, sin .arqux del emisor
mkdir -p audit/.arqux/keys
cp bundle.cortex emisor.pub audit/ && mv audit/emisor.pub audit/.arqux/keys/
cd audit

pip install arqux
arqux policy verify bundle.cortex
# → SIGNATURE_VALID key_id:8f3a…   (exit 0)

# Prueba de forja: un byte añadido invalida
echo 'AUD:e_9999{agent:"mallory"}' >> bundle.cortex
arqux policy verify bundle.cortex
# → ERR_INVALID_SIGNATURE: signature does not match document payload  (exit 1)
```

Sin `--key`, `verify` resuelve la pública buscando líneas `public:` en `.arqux/keys/` junto al documento — el auditor no necesita el keypair completo ni el repositorio.

## Mecanismo → control de cumplimiento

Lenguaje prudente: ArqUX **aporta evidencia para** estos controles; no certifica cumplimiento de ningún marco.

| Mecanismo | Qué aporta evidencia para | Verificación |
|---|---|---|
| Bundle `EVD` + spans `SPN` con SHA-256 del timelog fuente | Trazabilidad de ejecución — quién, cuándo, sobre qué artefacto (EU AI Act art. registro; ISO 27001 A.8.15 logging) | `arqux evidence export --out …` |
| Ed25519 `SIG:signature` | Integridad y no-repudio del artefacto exportado (custodia de evidencia) | `arqux policy verify` exit 0 / `ERR_INVALID_SIGNATURE` exit 1 |
| Gate `visibility:"private"` + `redacted:N` | Minimización de datos en export — lo privado no sale por defecto (principio GDPR de minimización) | `EXPORT_BLOCKED` exit 1 sin flag |
| Estado gobernado local (`.arqux/` en disco propio) | Residencia de datos — el estado del agente vive en infraestructura propia | inspección del filesystem |
| Journal `ERR_CONFLICT_VERSION` | Integridad de política compartida — divergencia detectada, no silenciada | `arqux push-delta` con base obsoleta |

## Límites honestos

Lo que esta evidencia **no** garantiza:

1. **Veracidad del contenido** — la firma prueba integridad y origen de clave, no que el agente dijera la verdad al registrar. Un evento falso firmado es un evento falso válido.
2. **Cobertura total** — el bundle incluye solo lo que los timelogs registraron en `$5` con sigilos `AUD`/`DEC`/`ERR`/`LOOP`. Acción sin evento = acción sin evidencia.
3. **Imposibilidad de `--allow-raw`** — el gate exige decisión humana, no la impide técnicamente. Un operador con acceso puede exportar lo privado; el control es de procedimiento y queda marcado (`raw:true`).
4. **Formato estándar** — el bundle es CODEC-CORTEX, no JSON/XML/SAML. Verificarlo requiere `pip install arqux` (o un parser del formato).
5. **Custodia de claves** — la clave privada es un archivo 0600. HSM/KMS/rotación institucional son responsabilidad del operador.

## Apéndice — qué revisa el auditor externo, paso a paso

1. Recibir `bundle.cortex` + archivo `public:` — **sin** `seed:`. Si llega el seed, el canal de entrega está mal y se reporta.
2. `EVD:bundle{…}` — leer `spans`, `events`, `redacted`, `raw`. `raw:true` exige explicación del emisor.
3. `arqux policy verify bundle.cortex` con la pública en `.arqux/keys/` → `SIGNATURE_VALID`.
4. Prueba negativa: alterar una línea → `ERR_INVALID_SIGNATURE`. Confirma que la verificación no es ceremonial.
5. Por cada `SPN:` — el `sha256` enlaza el span con su timelog fuente; si se requiere, el emisor puede regenerar el hash del timelog original para corroborar.
6. Discrepancias (`ERR_KEY_MISMATCH`, `ERR_NO_SIGNATURE`, `ERR_KEY_NOT_FOUND`) se escalan al emisor con la salida exacta.

## Referencias

- `THREAT_MODEL.md` — modelo de amenazas con mecanismos y verificación
- `EVIDENCE.md` — catálogo de artefactos de evidencia con campos reales
- `docs/es/especificacion/formato.md` — formato CODEC-CORTEX

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
