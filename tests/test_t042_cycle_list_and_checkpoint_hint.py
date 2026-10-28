"""CYCLE-12 / BLP-027 — dos hallazgos del arranque del 2026-10-28.

1. ``cycle.list`` aceptaba ``status`` y lo ignoraba: ``open`` y ``closed``
   devolvían los mismos catorce ciclos.
2. El hint de ``cortex.checkpoint`` anunciaba ``;`` como separador, pero el
   parser lo conserva dentro del valor: un checkpoint con ``;`` reportaba
   éxito con ``obj``/``tasks``/``state`` vacíos.
"""

from __future__ import annotations

import re

import pytest

from arqux.handlers.cortex.checkpoint import checkpoint_handler
from arqux.handlers.cycle import close_cycle, create_cycle, list_cycles
from arqux.state import cycle_dir


@pytest.fixture
def two_cycles(arqux_env):
    first = create_cycle(name="CYCLE-ONE", path=str(arqux_env.proj_root),
                         ctx=arqux_env.gov_ctx).fields["cycle_id"]
    second = create_cycle(name="CYCLE-TWO", path=str(arqux_env.proj_root),
                          ctx=arqux_env.gov_ctx).fields["cycle_id"]
    return first, second


def _close(env, cycle_id):
    cdir = cycle_dir(env.proj_root / ".arqux", cycle_id)
    manifest = cdir / "MANIFEST.md"
    text = manifest.read_text(encoding="utf-8")
    closed = re.sub(r'status:\s*"?draft"?', 'status: "closed"', text, count=1)
    assert closed != text
    manifest.write_text(closed, encoding="utf-8")


class TestCycleListFilter:
    def test_open_excludes_closed(self, arqux_env, two_cycles):
        first, second = two_cycles
        _close(arqux_env, first)

        listed = list_cycles("open", path=str(arqux_env.proj_root),
                             ctx=arqux_env.gov_ctx).fields["cycles"]
        assert first not in listed
        assert second in listed

    def test_closed_returns_only_closed(self, arqux_env, two_cycles):
        first, second = two_cycles
        _close(arqux_env, first)

        listed = list_cycles("closed", path=str(arqux_env.proj_root),
                             ctx=arqux_env.gov_ctx).fields["cycles"]
        assert listed == [first]

    def test_no_filter_lists_everything(self, arqux_env, two_cycles):
        first, second = two_cycles
        listed = list_cycles(path=str(arqux_env.proj_root),
                             ctx=arqux_env.gov_ctx).fields["cycles"]
        assert {first, second} <= set(listed)

    def test_closing_a_cycle_moves_it_between_filters(self, arqux_env, two_cycles):
        first, _ = two_cycles
        cdir = cycle_dir(arqux_env.proj_root / ".arqux", first)
        (cdir / "MANIFEST.md").write_text(
            f'---\ncycle_id: "{first}"\nstatus: draft\n---\n## §1: Propósito\nTest\n',
            encoding="utf-8",
        )
        close_cycle(first, summary="cierre de prueba", path=str(arqux_env.proj_root),
                    ctx=arqux_env.gov_ctx)

        closed = list_cycles("closed", path=str(arqux_env.proj_root),
                             ctx=arqux_env.gov_ctx).fields["cycles"]
        assert first in closed


class TestCheckpointHint:
    def test_semicolon_is_not_advertised_as_a_separator(self, arqux_env):
        out = checkpoint_handler(
            content="fcs:seguir; obj:probar; tasks:none",
            path=str(arqux_env.proj_root),
        )
        assert "hint" in out.fields
        assert "';' is kept inside the value" in out.fields["hint"]
        assert "',' ';' newline" not in out.fields["hint"]

    def test_comma_separated_content_parses_without_hint(self, arqux_env):
        out = checkpoint_handler(
            content="fcs:seguir, obj:probar, tasks:none, state:active",
            path=str(arqux_env.proj_root),
        )
        assert "hint" not in out.fields
        assert out.fields["obj"] == "probar"
