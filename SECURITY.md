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

# Política de seguridad

## Versiones soportadas

| Versión | Soportada |
|---|---|
| 1.0.x | ✅ |
| ≤ 0.9.x | ❌ — actualiza a 1.0.x |

> Nota honesta: `pip install arqux` puede servir aún la serie 0.9.x desde PyPI mientras el repositorio declara 1.0.0. Solo la línea 1.0.x recibe correcciones de seguridad.

## Cómo reportar una vulnerabilidad

**Canal: GitHub Security Advisories (Private Vulnerability Reporting).**

1. Abre el repositorio [`FidelErnesto03/arqux`](https://github.com/FidelErnesto03/arqux).
2. Pestaña **Security** → **Advisories** → **Report a vulnerability**.
3. El reporte es privado por defecto: solo los mantenedores lo ven hasta la divulgación coordinada.

Incluye en el reporte:

- Descripción del impacto y condiciones para dispararlo
- Pasos de reproducción o PoC mínima
- Versión afectada (`arqux --version` / `pyproject.toml`)
- Archivos o handlers involucrados si los conoces

**No uses issues públicos ni PRs** para vulnerabilidades sin divulgar.

## Qué esperar (ventanas honestas, best effort)

Somos un proyecto pequeño; declaramos objetivos realistas, no SLA contractuales:

| Fase | Ventana objetivo |
|---|---|
| Acuse de recibo | ~7 días |
| Triaje y evaluación de severidad | ~14 días |
| Corrección + release | Según severidad; las críticas se priorizan |
| Divulgación coordinada | Tras el release del fix, acordada contigo |

Si la ventana se excede, un bump en el advisory es bienvenido — no publicites antes del acuerdo de divulgación.

## Alcance

**Reporta (in-scope):**

- Bypass del modelo de permisos (un AUDITOR ejecutando handlers mutantes)
- Bypass o debilidad de la verificación HMAC o de la frontera codec fail-closed
- Firmas Ed25519 aceptadas inválidas / integridad SHA-256 eludida
- Vulnerabilidades en dependencias core que afecten a ArqUX
- Escrituras gobernadas que evaden el check `secret_pattern` u otras reglas `enforce:CODE`

**No reportes aquí (out-of-scope):**

- Comportamiento indeseado de agentes LLM de terceros (hallucinations, jailbreaks del modelo)
- Vulnerabilidades de harness/clientes MCP externos, no del código de ArqUX
- Problemas de tus propias reglas de política o configuración
- Denegación de servicio por recursos del entorno del usuario

## Divulgación

Coordinada: publicamos el advisory junto con el fix, con crédito al reportero si lo desea. Pedimos no divulgar hasta entonces.

## Práctica propia

Este producto aplica a sí mismo lo que vende: políticas y evidencia de gobierno se firman con Ed25519 puro (REQ-12) y la integridad de archivos `.cortex` se verifica por SHA-256 (`arqux cortex-verify`). Si encuentras una forma de falsificar esa cadena de evidencia, es exactamente la clase de hallazgo que más nos interesa.

Ver también: [`THREAT_MODEL.md`](THREAT_MODEL.md) — modelo de amenazas completo · [`PERMISSIONS.md`](PERMISSIONS.md) — modelo de autorización.

<!-- DOC-FOOT -->
<hr>
<p align="center"><sub>ArqUX 1.0.0 · verificado 2026-11-15 · <a href="./docs/es/README.md">índice de documentación</a></sub></p>
<!-- /DOC-FOOT -->
