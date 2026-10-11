"""Optional bridge from comms messages to ArqUX governance.

Default OFF: comms never mutates governance on its own. When enabled, this
logs incoming messages to a local NDJSON audit trail and can later be wired
to the governance handlers (evidence/identity). Keeping it opt-in preserves
the local-first and separation-of-duties guarantees.
"""

from __future__ import annotations

import json
import time

from .config import redact, state_dir


class Bridge:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.logged = 0

    def record(self, msg: dict) -> dict:
        """Append ``msg`` to the local audit trail (NDJSON)."""
        path = state_dir() / "inbox_log.ndjson"
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({**msg, "logged": time.time()},
                                   ensure_ascii=False) + "\n")
            self.logged += 1
        except Exception as exc:  # noqa: BLE001
            return {"logged": False, "error": redact(repr(exc))}
        return {"logged": True}
