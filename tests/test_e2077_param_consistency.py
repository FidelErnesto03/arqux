"""E-2077 — inconsistent parameter names and silent argument loss.

``timelog.query(session=...)`` was swallowed silently, ``blueprint_id``
was rejected where ``bp_id`` was expected, and a typo fell to a cryptic
INTERNAL_ERROR TypeError. The dispatch layer now resolves known aliases
onto the declared signature and reports INVALID_ARGS naming the expected
parameters.
"""

from __future__ import annotations

import asyncio

from arqux.handlers.blueprint._read import read_blueprint
from arqux.handlers.blueprint.manage import update_blueprint
from arqux.handlers.session import pulse_compact
from arqux.handlers.timelog import query_handler
from arqux.server import _resolve_kwargs, _wrap_handler


def _call(name, fn, **kwargs):
    return asyncio.run(_wrap_handler(name, fn)(**kwargs))


class TestAliasResolution:
    def test_session_alias_maps_to_session_ref(self, arqux_env):
        resolved, unknown = _resolve_kwargs(
            query_handler, {"session": "SES001"}
        )
        assert resolved == {"session_ref": "SES001"}
        assert unknown == []

    def test_session_ref_maps_to_declared_session_id(self, arqux_env):
        resolved, unknown = _resolve_kwargs(
            pulse_compact, {"session_ref": "SES001"}
        )
        assert resolved == {"session_id": "SES001"}
        assert unknown == []

    def test_blueprint_id_maps_to_bp_id(self, arqux_env):
        resolved, unknown = _resolve_kwargs(
            read_blueprint, {"blueprint_id": "BLP-001"}
        )
        assert resolved == {"bp_id": "BLP-001"}
        assert unknown == []

    def test_project_dir_maps_to_path(self, arqux_env):
        resolved, unknown = _resolve_kwargs(
            query_handler, {"project_dir": "/tmp/x"}
        )
        assert resolved == {"path": "/tmp/x"}
        assert unknown == []

    def test_alias_call_reaches_the_handler(self, arqux_env):
        out = _call(
            "blueprint.read", read_blueprint,
            blueprint_id=arqux_env.bp_id, path=str(arqux_env.proj_root),
        )
        assert "OUT-ERROR" not in out, out


class TestUnknownParams:
    def test_unknown_param_is_invalid_args_with_expected(self, arqux_env):
        out = _call("timelog.query", query_handler, bogus_param="x")
        assert "code=INVALID_ARGS" in out
        assert "bogus_param" in out
        assert "session_ref" in out  # expected contract reported

    def test_missing_required_is_invalid_args_not_internal(self, arqux_env):
        out = _call("blueprint.update", update_blueprint)
        assert "code=INVALID_ARGS" in out
        assert "bp_id" in out

    def test_declared_kwargs_pass_through_unchanged(self, arqux_env):
        resolved, unknown = _resolve_kwargs(
            query_handler, {"session_ref": "SES002", "view": "session"}
        )
        assert resolved == {"session_ref": "SES002", "view": "session"}
        assert unknown == []
