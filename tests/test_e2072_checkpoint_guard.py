"""E-2072 — empty/partial checkpoints erased WRK:current.

On 2026-11-01 six checkpoints (E_0108–E_0113) were recorded without
``fcs``/``obj`` and silently wiped the agent's working memory. The
handler now refuses to write a WRK:current that cannot resume work,
and merges absent keys instead of clearing them.
"""

from __future__ import annotations

from arqux.handlers.cortex.checkpoint import checkpoint_handler
from arqux.state import crud_read

FULL = 'fcs:"foco",obj:"objetivo",tasks:"[PEND a]",state:"active"'
SEED = ('fcs:"foco previo",obj:"objetivo previo",'
        'tasks:"[DONE a]",state:"paused"')


def _wrk(env) -> dict:
    brain = env.proj_root / ".arqux" / "brain.cortex"
    entries = crud_read(brain, "$8/WRK:current")["entries"]
    return entries[0]["value"] if entries else {}


def _seed(env) -> None:
    out = checkpoint_handler(content=SEED, path=str(env.proj_root))
    assert out.profile == "OUT-WORK", out


class TestEmptyContent:
    def test_empty_string_is_rejected(self, arqux_env):
        _seed(arqux_env)
        out = checkpoint_handler(content="", path=str(arqux_env.proj_root))
        assert out.profile == "OUT-ERROR", out
        assert out.fields["code"] == "INVALID_ARGS"
        assert _wrk(arqux_env)["fcs"] == "foco previo"

    def test_whitespace_only_is_rejected(self, arqux_env):
        _seed(arqux_env)
        out = checkpoint_handler(content="   \n  ", path=str(arqux_env.proj_root))
        assert out.profile == "OUT-ERROR", out
        assert _wrk(arqux_env)["obj"] == "objetivo previo"

    def test_empty_wrk_envelope_is_rejected(self, arqux_env):
        _seed(arqux_env)
        out = checkpoint_handler(content="WRK:current{}",
                                 path=str(arqux_env.proj_root))
        assert out.profile == "OUT-ERROR", out
        assert _wrk(arqux_env)["fcs"] == "foco previo"


class TestPartialContent:
    def test_partial_without_usable_memory_is_rejected(self, arqux_env):
        # The fixture brain already holds a lifecycle WRK:current without
        # fcs/obj — a partial checkpoint must leave it untouched.
        before = dict(_wrk(arqux_env))
        out = checkpoint_handler(content='state:"active"',
                                 path=str(arqux_env.proj_root))
        assert out.profile == "OUT-ERROR", out
        assert out.fields["code"] == "INVALID_ARGS"
        assert _wrk(arqux_env) == before, "WRK:current no debió cambiar"

    def test_partial_update_merges_with_existing(self, arqux_env):
        _seed(arqux_env)
        out = checkpoint_handler(content='tasks:"[PEND b]"',
                                 path=str(arqux_env.proj_root))
        assert out.profile == "OUT-WORK", out
        value = _wrk(arqux_env)
        assert value["fcs"] == "foco previo"
        assert value["obj"] == "objetivo previo"
        assert value["tasks"] == "[PEND b]"
        assert value["state"] == "paused"

    def test_explicit_empty_key_does_not_wipe(self, arqux_env):
        _seed(arqux_env)
        out = checkpoint_handler(content='fcs:"",tasks:"[PEND c]"',
                                 path=str(arqux_env.proj_root))
        assert out.profile == "OUT-WORK", out
        value = _wrk(arqux_env)
        assert value["fcs"] == "foco previo"
        assert value["tasks"] == "[PEND c]"


class TestGluedKeys:
    def test_semicolon_glued_keys_fail_fast(self, arqux_env):
        _seed(arqux_env)
        out = checkpoint_handler(
            content="fcs:seguir; obj:probar; tasks:none",
            path=str(arqux_env.proj_root),
        )
        assert out.profile == "OUT-ERROR", out
        assert out.fields["code"] == "INVALID_ARGS"
        assert _wrk(arqux_env)["fcs"] == "foco previo"


class TestFullCheckpoint:
    def test_full_content_still_writes(self, arqux_env):
        out = checkpoint_handler(content=FULL, path=str(arqux_env.proj_root))
        assert out.profile == "OUT-WORK", out
        value = _wrk(arqux_env)
        assert value["fcs"] == "foco"
        assert value["obj"] == "objetivo"
        assert value["tasks"] == "[PEND a]"
