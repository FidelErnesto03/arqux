"""ARQUX Comms — extensión MCP de comunicación (Telegram-only).

Proceso MCP stdio aparte (patrón `arqux-voice`). NO toca el core ni su
presupuesto de handlers. Canal único: Telegram (Bot API + long-polling).
"""

from __future__ import annotations

__all__ = ["server", "config", "inbox", "telegram", "bridge", "doctor"]
