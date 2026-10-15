"""CYCLE-14 — end-to-end lifecycle over the real handlers.

Guards the whole state machine in one place, because the integration defects of
this cycle (transport key, ``$0`` section, switch reopening a closed session,
capture writing into a closed session, close capturing after the session was
closed) only appeared when the handlers were exercised together.
"""

from __future__ import annotations

from arqux.execution import bind_execution_key, mint_execution_key, reset_execution_key
from arqux.permissions import PermissionContext
from arqux.session_identity import get_session
from arqux.timelog_store import load


def _ctx(key: str) -> PermissionContext:
    return PermissionContext(agent_id="test-governor", role="governor", execution_key=key)


def test_full_lifecycle_opens_and_closes_blocks(arqux_env):
    from arqux.handlers.session import close, context_set
    from arqux.handlers.task import claim_task, complete_task, create_task

    key = mint_execution_key()
    token = bind_execution_key(key)
    try:
        ctx = _ctx(key)
        opened = context_set(project="test-proj", scope=arqux_env.cycle_id,
                             path=str(arqux_env.ws_root), ctx=ctx)
        sid = opened.fields["session_ref"]
        opened_at = opened.fields["opened_at"]

        created = create_task(obj="lifecycle probe", path=str(arqux_env.proj_root), ctx=ctx)
        tid = created.fields["task_id"]
        claim_task(tid, path=str(arqux_env.proj_root), ctx=ctx)
        complete_task(tid, evidence="done", path=str(arqux_env.proj_root), ctx=ctx)

        close(summary="cycle done", path=str(arqux_env.proj_root), ctx=ctx)

        doc = load(arqux_env.proj_root, sid, opened_at=opened_at)
        session_block = doc["blocks"][f"session_{sid}"]
        assert session_block["state"] == "closed", doc["blocks"]
        assert session_block["end"], doc["blocks"]

        task_blocks = {k: v for k, v in doc["blocks"].items()
                       if k != f"session_{sid}"}
        assert task_blocks, "the task activity left no block"
        for name, block in task_blocks.items():
            assert block["state"] == "closed", (name, block)
            assert block["end"], (name, block)

        assert get_session(arqux_env.proj_root, sid)["state"] == "closed"
    finally:
        reset_execution_key(token)


def test_switch_on_a_closed_session_leaves_it_closed(arqux_env):
    from arqux.handlers.identity.switch import switch
    from arqux.handlers.session import close, context_set

    key = mint_execution_key()
    token = bind_execution_key(key)
    try:
        ctx = _ctx(key)
        opened = context_set(project="test-proj", scope="CYCLE-TEST",
                             path=str(arqux_env.ws_root), ctx=ctx)
        sid = opened.fields["session_ref"]
        close(summary="done", path=str(arqux_env.proj_root), ctx=ctx)
        before = get_session(arqux_env.proj_root, sid)

        switch("alfred", path=str(arqux_env.proj_root), ctx=ctx)

        after = get_session(arqux_env.proj_root, sid)
        assert after["state"] == "closed"
        assert after["closed"] == before["closed"]
    finally:
        reset_execution_key(token)
