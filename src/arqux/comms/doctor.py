"""arqux comms-doctor — environment check for the comms extension."""

from __future__ import annotations

import sys

from .config import EGRESS_ENV, allowlist, egress_enabled, telegram_token


def _check(name: str, ok: bool, detail: str) -> dict:
    return {"check": name, "ok": ok, "detail": detail}


def run_checks() -> list[dict]:
    checks: list[dict] = []
    # dependency
    try:
        import httpx  # noqa: F401
        checks.append(_check("dep:httpx", True, "import ok"))
    except ImportError as exc:
        checks.append(_check("dep:httpx", False, str(exc)))
    # token
    tok = telegram_token()
    checks.append(_check("telegram:token", bool(tok),
                         "present" if tok else "MISSING (set "
                         "ARQUX_COMMS_TELEGRAM_TOKEN)"))
    # allowlist (fail-closed)
    alw = allowlist()
    checks.append(_check("allowlist", bool(alw),
                         f"{len(alw)} chat_id(s)" if alw else
                         "EMPTY (fail-closed: nobody allowed)"))
    # egress
    eg = egress_enabled()
    checks.append(_check("egress", True,
                         f"{'ON' if eg else 'OFF (default)'} "
                         f"[{EGRESS_ENV}]"))
    # connectivity (only when egress is on, to respect local-first)
    if tok and eg:
        try:
            import httpx
            r = httpx.get(
                f"https://api.telegram.org/bot{tok}/getMe", timeout=10)
            ok = r.status_code == 200 and r.json().get("ok")
            checks.append(_check("telegram:getMe", bool(ok),
                                 "reachable" if ok else f"HTTP {r.status_code}"))
        except Exception as exc:  # noqa: BLE001
            checks.append(_check("telegram:getMe", False, repr(exc)))
    else:
        checks.append(_check("telegram:getMe", True,
                             "skipped (egress off or no token)"))
    return checks


def run() -> None:
    checks = run_checks()
    fails = 0
    for c in checks:
        mark = "PASS" if c["ok"] else "FAIL"
        if not c["ok"]:
            fails += 1
        print(f"[{mark}] {c['check']:16} {c['detail']}")
    print(f"\n{fails} failure(s)" if fails else "\nall checks PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    run()
