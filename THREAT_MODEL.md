---
doc_type: canon
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
<p align="center"><sub>Canon · Normativo · ArqUX 1.0.0</sub></p>
<!-- /DOC-BRAND -->

# Modelo de amenazas de ArqUX

Modelo de amenazas vigente de ArqUX 1.0.0. Contrato con el evaluador de seguridad: cada control afirmado tiene un mecanismo implementado detrás y un comando que lo verifica; cada amenaza no cubierta se declara en fuera de alcance o riesgo residual. Si una fila no puede ejecutarse, el control no existe — está en residuales.

## Ámbito, actores y activos

**Activos protegidos**

| Activo | Ubicación | Por qué importa |
|---|---|---|
| Estado gobernado | `.arqux/**/*.cortex` (brain, blueprints, journal) | Alterarlo falsifica la verdad operativa del proyecto |
| Evidencia | timelogs `SES*.cortex`, PULSE (`AUD:*`), bundles `EVD` | Registro append-only de quién hizo qué; base de auditoría |
| Secretos de agente | `.arqux/secrets/<agent>.key` | Comprometerlo = suplantar al agente en handlers HMAC |
| Claves Ed25519 | archivo de clave externo al workspace (ruta del operador) | Firma de bundles y políticas; no-repudio |
| Journal de políticas | `journal.cortex` del workspace | Política autoritativa compartida entre clones |

**Actores de amenaza**

| Actor | Capacidad | Motivación |
|---|---|---|
| Proceso agente comprometido | Invocar handlers MCP, fijar variables de entorno | Mutar estado fuera de su rol, forjar evidencia |
| Usuario local malicioso | Acceso de lectura/escritura al filesystem | Alterar `.cortex`, recomputar sellos, leer secretos |
| Insider con rol governor | Todos los handlers | Abusar del rol, cubrir rastros |
| Atacante de cadena de suministro | Comprometer dependencia en PyPI | Ejecutar código en el proceso del agente |

## Fronteras de confianza

```
┌─────────────────────────────────────────────────────────┐
│ Agente (harness externo — NO es frontera de ArqUX)      │
└──────────────┬──────────────────────────────────────────┘
               │ MCP stdio · JSON-RPC · handler+permiso por llamada
┌──────────────▼──────────────────────────────────────────┐
│ arqux serve                                             │
│  · permissions.py: rol→denylist de invocaciones mutantes│
│  · security.py: HMAC agent_id|handler|ts|payload        │
│  · policy_engine.py: reglas enforce + check de secretos │
└──────────────┬──────────────────────────────────────────┘
               │ escritura atómica + flock
┌──────────────▼──────────────────────────────────────────┐
│ Filesystem (.arqux/)                                    │
│  · SHA-256 integrity header por .cortex                 │
│  · secretos 0600 · Ed25519 en artefactos firmados       │
└─────────────────────────────────────────────────────────┘
```

La frontera real es la llamada MCP: todo acceso a estado gobernado pasa por un handler con chequeo de permiso. El transporte es stdio — el servidor MCP no abre socket de red.

## Amenazas y controles

| # | Amenaza | Control | Mecanismo real | Verificación ejecutable |
|---|---|---|---|---|
| 1 | Suplantación de agente en handlers sensibles | Firma HMAC de la invocación | `security.py: sign_request/verify_request` — firma `agent_id\|handler\|timestamp\|payload_hash`, comparación `hmac.compare_digest` | `tests/test_security_hmac.py` |
| 2 | Replay de invocación firmada | Ventana de frescura | `MAX_CLOCK_SKEW_SECONDS = 300`; skew mayor → `IdentityVerificationError` | `tests/test_security_hmac.py` |
| 3 | Auditor ejecuta handler mutante | Denylist por invocación mutante | `permissions.py: _is_mutating_invocation` — auditor denegado en mutación, permitido en preview/lectura; `ROLE_CONTROL_HANDLERS={identity.switch}` | `tests/test_auditor_readonly.py`, `tests/test_permissions.py` |
| 4 | Escalación de rol sin enforcement | Modo estricto | `ARQUX_STRICT_ROLES=1` activa el chequeo; `PermissionDenied` → `PERMISSION_DENIED` en CORTEX-OUT | `tests/e2e/test_security_controls.py` |
| 5 | Secreto escrito en artefacto | Check pre-escritura | `policy_engine.py: _check_secret_pattern` registrado en `CODE_CHECKS` — detecta patrones de secreto en contenido | `tests/e2e/test_security_controls.py` |
| 6 | Alteración de `.cortex` en disco | Sello de integridad SHA-256 | `security.py: hash_cortex/inject_hash_header/verify_cortex` — mismatch → `TamperError` | `arqux cortex-verify <file>`; `tests/test_security_cortex.py` |
| 7 | Repudio de evidencia exportada | Firma Ed25519 del documento | `signing.py` — Ed25519 puro RFC 8032 sin dependencia externa; firma los bytes canónicos excluyendo líneas `SIG:signature`; alteración → `ERR_INVALID_SIGNATURE` | `arqux policy keygen` + `sign <doc> --key <k>` + `verify <doc> --key <k>` |
| 8 | Colisión de IDs en escritura concurrente | Lock de archivo | `concurrency.py: file_lock()` — `fcntl.flock(LOCK_EX)` cross-process en POSIX, `TimeoutError` a los 10 s | `tests/test_concurrency.py` |
| 9 | Sobrescritura de journal con base obsoleta | Optimistic locking | `journal.py: push_delta` exige `base_version` == versión actual; rechazo → `ERR_CONFLICT_VERSION` para triaje humano | `tests/test_req_m3.py` |
| 10 | Fuga de datos privados en export | Gate de privacidad fail-closed | `evidence_export.py: export_bundle` — entradas marcadas `visibility:"private"` no salen del workspace: sin `--redact-private` ni `--allow-raw` → `PermissionError`; `EVD:bundle` registra `redacted`/`raw` | `arqux evidence export --out <f> --redact-private`; `tests/test_req_m3.py` |
| 11 | Clave de agente legible por terceros | Permisos de store | `security.py: save_agent_secret` fuerza `chmod 0600`; `_load_agent_secret` advierte si el modo es más permisivo | inspección de `.arqux/secrets/` |

## Fuera de alcance

Declarado, no implícito. Estas amenazas son reales pero **no las cubre ArqUX**:

| Amenaza | Por qué está fuera |
|---|---|
| Gestión institucional de claves (HSM, KMS, rotación corporativa) | `generate_keypair`/`load_keypair` operan sobre archivos; la custodia de la clave privada Ed25519 es responsabilidad del operador |
| Transporte de red del journal | La sincronización entre clones se delega al transporte del operador (git, rsync, etc.); ArqUX garantiza conflicto detectable (`ERR_CONFLICT_VERSION`), no confidencialidad en tránsito |
| Compromiso del harness/runtime del agente | ArqUX gobierna el estado, no el proceso que lo invoca; un agente con el secreto de un governor es indistinguible del governor |
| Hardening del sistema operativo anfitrión | Usuarios con mismo UID o root leen `.arqux/secrets/` y recomputan sellos; se asume host razonablemente confiable |

## Riesgos residuales

| Residual | Estado honesto | Mitigación disponible |
|---|---|---|
| Sello SHA-256 convive con el contenido en el mismo archivo | Quien escribe el archivo recomputa el sello — el sello detecta corrupción y edición casual, no adversario con escritura total | Ed25519 con clave privada fuera del archivo: no-repudio real |
| Rol por defecto sin enforcement | Sin `ARQUX_STRICT_ROLES=1`, el modelo es legacy (bypass governor) | Exportar la variable en todo despliegue serio |
| Ventana de replay de 5 minutos | Una invocación capturada es rejugable dentro del skew | Reducir `MAX_CLOCK_SKEW_SECONDS`; NTP en agentes |
| Lock solo intra-proceso en Windows | `fcntl` no existe en Windows; el fallback es `threading.Lock` | No operar procesos ArqUX concurrentes en Windows |
| Dependencias transitivas opacas | `pip-audit` limpio sobre directas; el grafo transitivo no está congelado | Auditar periódicamente; fijar lockfile en despliegues |
| Secreto legible por mismo UID/root | 0600 no protege contra el propio usuario ni privilegiados | Cifrado de disco a nivel OS, shells restringidos |

## Cómo verificar este documento

```bash
# Integridad de un .cortex (amenaza 6)
arqux cortex-verify .arqux/brain.cortex

# Firma Ed25519 de un artefacto (amenaza 7)
# `sign` anexa la línea SIG:signature al documento — trabajar sobre copia
arqux policy keygen /tmp/demo.key
cp EVIDENCE.md /tmp/evidence-demo.md
arqux policy sign /tmp/evidence-demo.md --key /tmp/demo.key
arqux policy verify /tmp/evidence-demo.md --key /tmp/demo.key
# → SIGNATURE_VALID (exit 0); cualquier byte alterado → ERR_INVALID_SIGNATURE (exit 1)

# Gate de privacidad en export (amenaza 10)
arqux evidence export --out /tmp/bundle.cortex --redact-private

# Denegación de auditor en handler mutante (amenazas 3-4)
ARQUX_STRICT_ROLES=1 ARQUX_AGENT_ROLE=auditor arqux serve
# → invocar cualquier handler mutante devuelve PERMISSION_DENIED

# Suite de controles completa
uv run pytest tests/test_security.py tests/test_security_hmac.py \
  tests/test_security_cortex.py tests/test_auditor_readonly.py \
  tests/test_permissions.py tests/e2e/test_security_controls.py
```

## Qué este documento no es

- No es una guía operativa de cumplimiento — eso pertenece a la guía de evidencia para CISO.
- No es una política de reporte de vulnerabilidades — eso es `SECURITY.md`.
- No certifica controles de terceros — cada fila describe mecanismo propio y verificable, no servicios externos.

## Referencias

- `EVIDENCE.md` — catálogo de evidencia con campos reales
- `SECURITY.md` — canal de reporte de vulnerabilidades
- `PERMISSIONS.md` — modelo de permisos y tiers de enforcement
- `docs/es/especificacion/` — canon CORTEX normativo

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="./docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
