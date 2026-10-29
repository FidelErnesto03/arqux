"""Los dos issues de EXPERTA del 2026-10-28 sobre ``cortex.checkpoint``.

1. El campo ``state`` se truncaba en la primera coma aunque viniera entre
   comillas: el parser protegía ``[...]`` pero no las cadenas. Se perdían
   pendientes y el handler respondía ``ok``.
2. ``WRK:current`` mezclaba dos épocas: ``fcs/tasks/state`` del turno actual
   con ``event``/``updated``/``current`` del último handler de ciclo de vida.
"""

from __future__ import annotations

from arqux.handlers.cortex.checkpoint import checkpoint_handler
from arqux.state import crud_read

ISSUE_SAMPLE = (
    'fcs:"diseno funcional v1.3",'
    'obj:"cerrar LAB-311",'
    'tasks:"[DONE a,DONE b]",'
    'state:"SES019 retomada en exec-798cff20;PENDIENTE:BLP-003 ready,'
    'BLP-001 close,LNG protocolo pendientes"'
)


def _wrk(env) -> dict:
    brain = env.proj_root / ".arqux" / "brain.cortex"
    entries = crud_read(brain, "$8/WRK:current")["entries"]
    assert entries, "WRK:current no se escribió"
    return entries[0]["value"]


class TestQuotedValues:
    def test_state_keeps_its_commas(self, arqux_env):
        out = checkpoint_handler(content=ISSUE_SAMPLE, path=str(arqux_env.proj_root))
        assert out.profile == "OUT-WORK", out

        value = _wrk(arqux_env)
        assert value["state"].endswith("LNG protocolo pendientes")
        assert "BLP-001 close" in value["state"]
        assert value["tasks"] == "[DONE a,DONE b]"

    def test_a_simple_quoted_comma_survives(self, arqux_env):
        checkpoint_handler(content='fcs:"x",state:"a,b,c"',
                           path=str(arqux_env.proj_root))
        assert _wrk(arqux_env)["state"] == "a,b,c"

    def test_unterminated_quote_is_reported_not_written(self, arqux_env):
        out = checkpoint_handler(content='state:"sin cerrar',
                                 path=str(arqux_env.proj_root))
        assert out.profile == "OUT-ERROR", out
        assert out.fields["code"] == "INVALID_ARGS"
        assert "unterminated" in out.message


class TestCurrentEvent:
    def test_checkpoint_marks_itself_as_the_current_event(self, arqux_env):
        checkpoint_handler(content='fcs:"arreglar el parser",obj:"x"',
                           path=str(arqux_env.proj_root))

        value = _wrk(arqux_env)
        assert value["event"] == "cortex.checkpoint"
        assert value["current"].startswith("arreglar el parser")
        assert value["updated"] == value["last_turn"]

    def test_a_stale_lifecycle_event_is_replaced(self, arqux_env):
        from arqux.state import crud_add

        brain = arqux_env.proj_root / ".arqux" / "brain.cortex"
        crud_add(str(brain), "$8", "WRK", "current", {
            "fcs": "viejo", "obj": "viejo", "tasks": "viejo", "state": "viejo",
            "last_turn": "2026-10-20T00:00:00Z",
            "event": "blueprint.complete",
            "updated": "2026-10-27T16:47:08Z",
            "current": "blueprint.complete: BLP BLP-002 completed",
        }, create_section=True, force=True)

        checkpoint_handler(content='fcs:"foco nuevo"', path=str(arqux_env.proj_root))

        value = _wrk(arqux_env)
        assert value["event"] == "cortex.checkpoint"
        assert value["current"] == "foco nuevo"
        assert value["updated"] != "2026-10-27T16:47:08Z"
