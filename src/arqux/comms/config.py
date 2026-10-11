"""Runtime configuration for arqux-comms.

Secrets and policy come from the environment (never the repo):
  * ARQUX_COMMS_TELEGRAM_TOKEN — BotFather token (secret).
  * ARQUX_COMMS_ALLOWLIST      — comma/semicolon separated chat_ids.
  * ARQUX_COMMS_EGRESS         — on|off (default OFF, local-first).
"""

from __future__ import annotations

import os
from pathlib import Path

TELEGRAM_TOKEN_ENV = "ARQUX_COMMS_TELEGRAM_TOKEN"
ALLOWLIST_ENV = "ARQUX_COMMS_ALLOWLIST"
EGRESS_ENV = "ARQUX_COMMS_EGRESS"
DEFAULT_EGRESS = "off"

CHANNELS = ("telegram",)


def telegram_token() -> str | None:
    """Bot token (secret) or None when unset."""
    val = os.environ.get(TELEGRAM_TOKEN_ENV)
    return val.strip() if val and val.strip() else None


def allowlist() -> set[str]:
    """Allowed chat_ids (fail-closed: empty means nobody is allowed)."""
    raw = os.environ.get(ALLOWLIST_ENV) or ""
    return {x.strip() for x in raw.replace(";", ",").split(",") if x.strip()}


def egress_enabled() -> bool:
    """True only when egress is explicitly turned on."""
    val = (os.environ.get(EGRESS_ENV) or DEFAULT_EGRESS).strip().lower()
    return val in ("on", "1", "true", "yes")


def state_dir() -> Path:
    """Local state dir (offset, logs). Never inside the repo."""
    d = Path.home() / ".local" / "share" / "arqux" / "comms"
    d.mkdir(parents=True, exist_ok=True)
    return d


def redact(text: str) -> str:
    """Mask any occurrence of the token — never leak it in logs."""
    tok = telegram_token()
    if tok and tok in text:
        return text.replace(tok, "***")
    return text
