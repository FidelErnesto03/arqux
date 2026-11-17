---
doc_type: reference
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
<p align="center"><sub>Referencia · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Formatos de artefactos de producto

Especificación de los artefactos `.cortex` que ArqUX 1.0.0 produce como salida: sello de ciclo, bundle de evidencia, journal de políticas, documento firmado y reporte HCORTEX. Cada formato declara su productor, estructura real capturada, política de privacidad y verificación ejecutable. El dialecto base CORTEX (sigilos, secciones, tipos) pertenece a `docs/es/especificacion/formato.md` — este documento cubre las instancias concretas.

## Resumen

| Artefacto | Productor | Verificador |
|---|---|---|
| `seal.cortex` | `cycle.close` (REQ-03) | `arqux cortex-verify` → `ERR_HASH_MISMATCH` |
| `bundle.cortex` | `arqux evidence export` (REQ-11) | `arqux policy verify` tras firmar |
| `journal.cortex` | `arqux push-delta` (REQ-13) | `arqux pull-policy` + `ERR_CONFLICT_VERSION` |
| Documento firmado | `arqux policy sign` (REQ-12) | `arqux policy verify` → `SIGNATURE_VALID` |
| Reporte HCORTEX | `arqux review --cycle` (REQ-09) | `arqux from-hcortex` (round-trip) |

## 1. `seal.cortex` — sello de ciclo cerrado

Al cerrar un ciclo, cada artefacto `.cortex` del directorio del ciclo se hashea en disco; el sello raíz es el SHA-256 sobre los digests ordenados por archivo.

```cortex
$0
$0:format{cortex:1.0, encoding:UTF-8}

# -- $0: GLOSSARY --
# SEL | seal   | attrs | H | Root seal of a closed cycle
# HSH | hash   | attrs | M | Per-artifact SHA-256 record
SEL:sel_contract{type:"attrs", weight:"H", focus:"seal_sha256", fields:"cycle:text|seal_sha256:text|artifacts:int", desc:"Cycle seal", open:true}
HSH:hsh_contract{type:"attrs", weight:"M", focus:"file", fields:"file:text|sha256:text", desc:"Artifact hash", open:true}

$1: SEAL
SEL:seal{cycle:"CYCLE-99", seal_sha256:"0b7b7e34…8103dba", artifacts:2}
HSH:cycle_cortex{file:"cycle.cortex", sha256:"148fcf40…1e3cb"}
HSH:tasks_t1_cortex{file:"tasks/t1.cortex", sha256:"37be4d77…eba35"}
```

| Campo | Tipo | Significado |
|---|---|---|
| `SEL:seal.cycle` | texto | Nombre del ciclo sellado |
| `SEL:seal.seal_sha256` | hex 64 | SHA-256 sobre la concatenación de digests ordenados |
| `SEL:seal.artifacts` | entero | Artefactos cubiertos |
| `HSH:*.file` | ruta relativa | Artefacto dentro del directorio del ciclo |
| `HSH:*.sha256` | hex 64 | Digest del archivo en disco al cierre |

**Verificación**: `arqux cortex-verify seal.cortex` recomputa cada `HSH` contra el archivo en disco. Deriva → `FAIL: [ERR_HASH_MISMATCH] <file>: recorded=… actual=…` (exit 1). El `seal_sha256` raíz también queda en el front-matter del `MANIFEST.md` del ciclo.

**Privacidad**: nombres de archivo y hashes solamente — sin contenido.

## 2. `bundle.cortex` — export de evidencia

Producido por `arqux evidence export`. Empaqueta spans de sesión y eventos de gobierno de los timelogs `SES*.cortex`.

```cortex
$0

$0:format{cortex:1.0, encoding:UTF-8}

ARQX:arqx_contract{…}   EVD:evd_contract{…}   SPN:spn_contract{…}
AUD:aud_contract{…}     DEC:dec_contract{…}   ERR:err_contract{…}
LOOP:loop_contract{…}

$19: ARQUX METADATA
ARQX:artifact{level:0, name:"evidence-2026-11-15T21:52:10Z", usage:"export", kind:"bundle"}

$1: EVIDENCE
EVD:bundle{generated:"2026-11-15T21:52:10Z", project:"ciso-sbx", spans:1, events:2, redacted:1, raw:false}

$2: SPANS
SPN:ses999{session:"SES999", identity:"alfred", opened:"2026-11-15T10:00:00Z", closed:"2026-11-15T11:00:00Z", sha256:"2a802e5f5def5127", source:"SES999_20261115_100000.cortex"}

$3: EVENTS
AUD:e_0001{ts:"2026-11-15T10:05:00Z", agent:"alfred", action:"blueprint.claim", target:"BLP-016"}
ERR:e_0003{ts:"2026-11-15T10:30:00Z", code:"ERR_DEMO", recovered:"true"}
```

| Campo | Tipo | Privacidad |
|---|---|---|
| `EVD:bundle.generated/project` | texto | Público |
| `EVD:bundle.spans/events/redacted` | entero | Público — contadores, no contenido |
| `EVD:bundle.raw` | bool | `true` = exportó privado verbatim (exige justificación) |
| `SPN:*.sha256` | hex 16 | Digest del timelog fuente — enlaza span↔origen |
| Eventos `$3` | sigilos `AUD/DEC/ERR/LOOP` | Solo sección `$5` del timelog; `visibility:"private"` bloqueado o redactado |

**Política de privacidad**: sin flag → `EXPORT_BLOCKED` (exit 1) si existe cualquier línea `visibility:"private"` en los timelogs. `--redact-private` excluye esas entradas y registra el conteo. `--allow-raw` las incluye verbatim — uso de auditoría, queda marcado `raw:true`.

**Verificación**: tras firmar, `arqux policy verify bundle.cortex` → `SIGNATURE_VALID`. Estructura parseable por cualquier lector CODEC-CORTEX.

## 3. `journal.cortex` — journal autoritativo de políticas

Producido por `arqux push-delta`. Ubicación: `.arqux/journal/journal.cortex` del workspace. Optimistic locking: un delta solo se aplica si su `base_version` iguala la versión vigente.

```cortex
$1: JOURNAL
JRN:journal{version:1, deltas:1, rules:1, updated:"2026-11-15T21:54:30Z"}

$2: DELTAS
DLT:ws-demo_1{workspace:"ws-demo", base_version:0, new_version:1, rules:1, sha256:"ce3f6a48b374f3a8", applied:"2026-11-15T21:54:30Z"}

$3: POLICY
RUL:no_raw_private{check:"secret_pattern", action:"deny", when:"export", desc:"deny raw private fields"}
```

| Campo | Tipo | Significado |
|---|---|---|
| `JRN:journal.version` | entero | Versión vigente — contador monótono del optimistic lock |
| `JRN:journal.deltas/rules` | entero | Contadores de las secciones `$2`/`$3` |
| `DLT:*.base_version/new_version` | entero | Versión sobre la que el emisor construyó el delta |
| `DLT:*.sha256` | hex 16 | Digest del delta aplicado — trazabilidad |
| `RUL:*` | attrs | Regla enforce vigente (`check`, `action`, `when`) |

**Verificación**: `arqux pull-policy` renderiza la política vigente; `arqux push-delta --base <obsoleto>` → `ERR_CONFLICT_VERSION: journal is at version 1, delta claims base 0 — human triage required` (exit 1). La divergencia es detectable — nunca se sobrescribe en silencio.

**Privacidad**: solo reglas de política — no transporta evidencia ni datos de sesión.

## 4. Documento firmado — `SIG:signature`

`arqux policy sign <doc> --key <keypair>` anexa una entrada `SIG:signature` al final del documento e inyecta `SIG:sig_contract` en `$0` si falta (el documento firmado queda autocontenido).

```cortex
SIG:signature{algo:"ed25519", key_id:"e417895894ab81f5", payload_sha256:"818b5eaff4c92643…", sig:"51649b615c50682ef1…"}
```

| Campo | Tipo | Significado |
|---|---|---|
| `algo` | texto | Siempre `ed25519` (RFC 8032, implementación propia) |
| `key_id` | hex 16 | Primeros 16 chars de la clave pública |
| `payload_sha256` | hex 64 | Digest de los bytes canónicos firmados |
| `sig` | hex 128 | Firma Ed25519 sobre el texto canónico (documento completo menos líneas `SIG:`) |

**Verificación**: `arqux policy verify <doc>` → `SIGNATURE_VALID` (exit 0). Errores posibles: `ERR_INVALID_SIGNATURE` (contenido alterado), `ERR_NO_SIGNATURE` (sin entrada SIG), `ERR_KEY_MISMATCH` (firmado por otra clave), `ERR_KEY_NOT_FOUND` (sin pública resoluble en `.arqux/keys/`).

**Privacidad**: la firma prueba integridad y origen — no oculta contenido. La verificación externa usa solo la línea `public:` del keypair; el `seed:` nunca sale (ver `docs/es/guias/evidencia-y-cumplimiento.md`).

## 5. Reporte HCORTEX — `arqux review`

`arqux review --cycle <id>` renderiza el ciclo a Markdown para revisión humana. El bloque `<!-- HCORTEX v=0.1 t=canonical -->` embebe las entradas CORTEX como comentarios — el reporte es **round-trippable**: `arqux from-hcortex reporte.md` recompila el `.cortex` original.

```markdown
# Cycle Review — CYCLE-16

| Field | Value |
|---|---|
| Status | active |
| Entries | 2 |

## Evidence (HCORTEX — round-trippable)

<!-- HCORTEX v=0.1 t=canonical -->
<!-- glossary
$0
$0:format{cortex:1.0,encoding:UTF-8}
ARQX:arqx_contract{...}
-->
```

**Verificación**: `arqux from-hcortex <reporte.md>` regenera el artefacto — la forma humana y la máquina no divergen.

**Privacidad**: refleja el contenido del ciclo — las mismas reglas de publicación del proyecto aplican.

## Qué no cubre esta especificación

Formatos internos de gobernanza (brain, timelogs, blueprints, handoffs) pertenecen al canon en `docs/es/especificacion/`. Versiones: esta especificación describe ArqUX 1.0.0 — un artefacto de versión distinta puede variar; el campo `ARQX:artifact` y `EVD:bundle` declaran su propio contexto.

## Referencias

- `docs/es/especificacion/formato.md` — dialecto CORTEX base
- `docs/es/guias/evidencia-y-cumplimiento.md` — flujo CISO completo con estos artefactos
- `THREAT_MODEL.md` — mecanismos de integridad detrás de cada formato

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="../../../docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
