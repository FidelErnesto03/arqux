#!/usr/bin/env python3
"""Generate the permissions table embedded in PERMISSIONS.md.

Emits one row per handler in the live registry:
    | Handler | Rol mínimo | HMAC | Condición |

Role minimum derives from permissions.py sets:
    - GOVERNOR_ONLY          → GOVERNOR
    - MUTATING_HANDLERS      → EXECUTOR  (auditor denied)
    - CONDITIONAL_MUTATING   → EXECUTOR* (auditor denied only when the
                               listed flags are truthy and not dry_run)
    - everything else        → AUDITOR   (read-only allowed)
    - HMAC_REQUIRED          → HMAC column = sí

Regeneration is deterministic: same registry + same permissions → same output.

Usage:
    python scripts/generate_permissions_md.py [--lang es|en] [--write FILE]

Without --write the fragment goes to stdout (manual paste between the
GENERATED:PERMISSIONS_TABLE markers). With --write the block between those
markers in FILE is replaced in place — the EN twin lives at
docs/en/root/PERMISSIONS.md and regenerates with --lang en.
"""
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from arqux.handlers import REGISTRY  # noqa: E402
from arqux.permissions import (  # noqa: E402
    CONDITIONAL_MUTATING,
    GOVERNOR_ONLY,
    HMAC_REQUIRED,
    MUTATING_HANDLERS,
)

I18N = {
    "es": {
        "comment": "generado desde REGISTRY + permissions.py",
        "header": "| Handler | Rol mínimo | HMAC | Condición |",
        "hmac_yes": "sí",
        "hmac_no": "no",
        "gov_only": "solo gobernador",
        "mutates": "muta — auditor denegado",
        "read": "lectura",
        "no_flag": "sin flag — muta siempre; dry_run/preview permiten lectura",
        "except": "salvo",
        "denied_if": "auditor denegado si",
    },
    "en": {
        "comment": "generated from REGISTRY + permissions.py",
        "header": "| Handler | Minimum role | HMAC | Condition |",
        "hmac_yes": "yes",
        "hmac_no": "no",
        "gov_only": "governor only",
        "mutates": "mutates — auditor denied",
        "read": "read",
        "no_flag": "no flag — always mutates; dry_run/preview allow reads",
        "except": "except",
        "denied_if": "auditor denied if",
    },
}

BEGIN = "<!-- GENERATED:PERMISSIONS_TABLE"
END = "<!-- /GENERATED:PERMISSIONS_TABLE -->"


def _condition(flags: tuple[str, ...], t: dict) -> str:
    if not flags:
        return t["no_flag"]
    parts = []
    for flag in flags:
        if flag.startswith("!"):
            parts.append(f"{t['except']} `{flag[1:]}`")
        else:
            parts.append(f"`{flag}`")
    return t["denied_if"] + " " + " ∧ ".join(parts)


def fragment(lang: str) -> str:
    t = I18N[lang]
    rows: list[str] = []
    for name in sorted(REGISTRY):
        if name in GOVERNOR_ONLY:
            role, cond = "GOVERNOR", t["gov_only"]
        elif name in MUTATING_HANDLERS:
            role, cond = "EXECUTOR", t["mutates"]
        elif name in CONDITIONAL_MUTATING:
            role, cond = "EXECUTOR*", _condition(CONDITIONAL_MUTATING[name], t)
        else:
            role, cond = "AUDITOR", t["read"]
        hmac = t["hmac_yes"] if name in HMAC_REQUIRED else t["hmac_no"]
        rows.append(f"| `{name}` | {role} | {hmac} | {cond} |")
    lines = [
        f"<!-- {len(rows)} handlers — {t['comment']} -->",
        t["header"],
        "|---|---|---|---|",
        *rows,
    ]
    return "\n".join(lines) + "\n"


def write_block(path: Path, lang: str) -> None:
    """Replace the GENERATED block in `path` with the fragment for `lang`."""
    text = path.read_text(encoding="utf-8")
    begin = text.find(BEGIN)
    end = text.find(END)
    if begin == -1 or end == -1 or end < begin:
        raise SystemExit(f"{path}: GENERATED:PERMISSIONS_TABLE markers not found")
    line_end = text.find("\n", begin)
    head = text[: line_end + 1]
    tail = text[end:]
    path.write_text(head + fragment(lang) + tail, encoding="utf-8")
    print(f"{path}: permissions table regenerated ({lang}, {len(REGISTRY)} handlers)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lang", choices=sorted(I18N), default="es")
    ap.add_argument("--write", type=Path, default=None,
                    help="inject the fragment between GENERATED markers in FILE")
    args = ap.parse_args()
    if args.write:
        write_block(args.write, args.lang)
    else:
        print(fragment(args.lang), end="")


if __name__ == "__main__":
    main()
