"""Regression: anti-corruption guards for governance writers (BLP-014).

Covers the defects from issue ``2026-10-01-corrupcion-silenciosa``:
- D1: ``blueprint.update`` must reject destructive content (headers/markers)
  and never persist an unbalanced marker structure.
- D2: ``cortex.entry.update set_`` must parse respecting quotes/brackets
  (no phantom attrs) and reject malformed input.
- D3: ``cortex.entry.add`` accepts ``content`` with sigil/name derived.
- D4: ``cortex.learn`` accepts a ``content`` kwarg.
"""

from __future__ import annotations

import re

from arqux.constants import OUT_ERROR
from arqux.handlers.blueprint.manage import update_blueprint
from arqux.handlers.cortex.entries import (
    _parse_set,
    entry_add_handler,
    entry_update_handler,
)


def _bp_file(arqux_env, bp_id: str):
    return (
        arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id
        / "blueprints" / f"{bp_id}.md"
    )


# --- D1: blueprint.update guards -------------------------------------------


def test_blueprint_update_rejects_header_content(arqux_env) -> None:
    r = update_blueprint(
        arqux_env.bp_id, section="7", content="intro text\n## §7: injected\nx",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    assert r.profile == OUT_ERROR, r.to_text()
    assert "INVALID_ARGS" in r.to_text()


def test_blueprint_update_rejects_marker_content(arqux_env) -> None:
    r = update_blueprint(
        arqux_env.bp_id, section="7", content="text <!-- /BLP:7 --> more",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    assert r.profile == OUT_ERROR, r.to_text()


def test_blueprint_update_keeps_marker_parity(arqux_env) -> None:
    update_blueprint(
        arqux_env.bp_id, section="6", content="**Dentro:** x",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    text = _bp_file(arqux_env, arqux_env.bp_id).read_text(encoding="utf-8")
    opens = len(re.findall(r"<!--\s*BLP:\w+\s*-->", text))
    closes = len(re.findall(r"<!--\s*/BLP:\w+\s*-->", text))
    assert opens == closes, "marker pairs unbalanced"
    assert opens >= 18


# --- D2: cortex.entry.update set_ parser -----------------------------------


def test_parse_set_commas_inside_quotes() -> None:
    d = _parse_set('summary:["a, b, c"], blps:["x"]')
    assert list(d.keys()) == ["summary", "blps"]
    assert d["summary"] == '["a, b, c"]'


def test_parse_set_brackets_and_colons() -> None:
    d = _parse_set("tags:[a, b, c]")
    assert d == {"tags": "[a, b, c]"}
    d2 = _parse_set("state:active")
    assert d2 == {"state": "active"}


def test_parse_set_rejects_garbage() -> None:
    import pytest

    with pytest.raises(ValueError):
        _parse_set("no-colon-here")


def test_entry_update_set_quoted_commas(arqux_env) -> None:
    f = arqux_env.proj_root / "t1.cortex"
    f.write_text('$0\n\n$1: X\n\nHOF:handoff{summary:"a", blps:"x"}\n', encoding="utf-8")
    r = entry_update_handler(
        str(f), "$1/HOF:handoff", set_='summary:"a, b, c", blps:"y"', ctx=arqux_env.gov_ctx
    )
    assert "ok" in r.to_text(), r.to_text()
    text = f.read_text(encoding="utf-8")
    assert text.count("summary") == 1, "phantom attrs / duplicated key"
    assert "a, b, c" in text


def test_entry_update_invalid_set(arqux_env) -> None:
    f = arqux_env.proj_root / "t2.cortex"
    f.write_text('$0\n\n$1: X\n\nHOF:handoff{a:1}\n', encoding="utf-8")
    r = entry_update_handler(str(f), "$1/HOF:handoff", set_="garbage", ctx=arqux_env.gov_ctx)
    assert r.profile == OUT_ERROR, r.to_text()


# --- D3: cortex.entry.add content-only -------------------------------------


def test_entry_add_schema_sigil_name_optional() -> None:
    from arqux.handlers.cortex import handler_schemas

    schema = next(s for s in handler_schemas if s["name"] == "cortex.entry.add")
    assert schema["input_schema"]["required"] == ["path"]


def test_entry_add_content_only(arqux_env) -> None:
    f = arqux_env.proj_root / "t3.cortex"
    f.write_text("$0\n\n$5: LEARN\n\n", encoding="utf-8")
    r = entry_add_handler(
        str(f), "$5", content='LNG:l1{type:"process", lesson:"x"}', ctx=arqux_env.gov_ctx
    )
    assert "ok" in r.to_text(), r.to_text()
    assert "l1" in r.to_text() or "LNG" in r.to_text()


# --- D4: cortex.learn content alignment ------------------------------------


def test_learn_accepts_content_kwarg() -> None:
    from arqux.handlers.cortex.learning import learn_scan_handler
    from arqux.permissions import PermissionContext

    ctx = PermissionContext(agent_id="t", role="governor")
    r = learn_scan_handler(content="scope:project", ctx=ctx)
    # must not raise TypeError; may return OUT-ERROR (engine/root unavailable)
    assert r.profile in ("OUT-WORK", "OUT-ERROR"), r.to_text()


# --- Evasion hardening (round 2) -------------------------------------------


def test_blueprint_update_rejects_mismatched_leading_header(arqux_env) -> None:
    r = update_blueprint(
        arqux_env.bp_id, section="6", content="## §7: HIJACK\n\nbody",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    assert r.profile == OUT_ERROR, r.to_text()


def test_blueprint_update_rejects_marker_no_space(arqux_env) -> None:
    r = update_blueprint(
        arqux_env.bp_id, section="7", content="<!--BLP:99-->x<!--/BLP:99-->",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    assert r.profile == OUT_ERROR, r.to_text()


def test_blueprint_update_rejects_header_variants(arqux_env) -> None:
    for variant in ("##§7: x", "# §7: x", "##  §7: x"):
        r = update_blueprint(
            arqux_env.bp_id, section="7", content=variant,
            path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
        )
        assert r.profile == OUT_ERROR, f"{variant!r} was accepted: {r.to_text()}"


def test_blueprint_update_allows_canonical_leading_header(arqux_env) -> None:
    r = update_blueprint(
        arqux_env.bp_id, section="7", content="## §7: Reglas\n\n1. r",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    assert "blueprint.update ok" in r.to_text(), r.to_text()


def test_parse_set_rejects_unbalanced_quote() -> None:
    import pytest

    with pytest.raises(ValueError):
        _parse_set('summary:"a, b')


def test_entry_update_rolls_back_phantom_attrs(arqux_env, monkeypatch) -> None:
    import arqux.handlers.cortex.entries as entries

    f = arqux_env.proj_root / "t4.cortex"
    original = '$0\n\n$1: X\n\nHOF:handoff{a:1}\n'
    f.write_text(original, encoding="utf-8")

    real = entries.crud_update

    def fake(path, selector, set_=None, replace_body=None, append=False, force=False):
        injected = {**(set_ or {}), "phantom": "9"}
        return real(path, selector, set_=injected, replace_body=replace_body, append=append, force=force)

    monkeypatch.setattr(entries, "crud_update", fake)
    r = entries.entry_update_handler(
        str(f), "$1/HOF:handoff", set_="a:2", ctx=arqux_env.gov_ctx
    )
    assert r.profile == OUT_ERROR, r.to_text()
    assert r.fields.get("rolled_back") is True
    # byte-faithful rollback: the original file text is restored
    assert f.read_text(encoding="utf-8") == original


# --- Round-2 evasions (N9, N10, N11) ---------------------------------------


def test_blueprint_update_rejects_lax_canonical_header(arqux_env) -> None:
    for variant in ("## § 7: DRIFT", "## §7 : DRIFT", "## §7\t: DRIFT"):
        r = update_blueprint(
            arqux_env.bp_id, section="7", content=variant,
            path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
        )
        assert r.profile == OUT_ERROR, f"{variant!r} accepted: {r.to_text()}"


def test_blueprint_update_note_guard(arqux_env) -> None:
    r1 = update_blueprint(
        arqux_env.bp_id, note="x\n## §7: DUP",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    assert r1.profile == OUT_ERROR, r1.to_text()

    r2 = update_blueprint(
        arqux_env.bp_id, note="x\n<!-- BLP:99 -->\n## §99: phantom\n<!-- /BLP:99 -->",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    assert r2.profile == OUT_ERROR, r2.to_text()


def test_entry_update_rollback_crlf_faithful(arqux_env, monkeypatch) -> None:
    import arqux.handlers.cortex.entries as entries

    f = arqux_env.proj_root / "t5.cortex"
    original = b'$0\r\n\r\n$1: X\r\n\r\nHOF:handoff{a:1}\r\n'
    f.write_bytes(original)

    real = entries.crud_update

    def fake(path, selector, set_=None, replace_body=None, append=False, force=False):
        injected = {**(set_ or {}), "phantom": "9"}
        return real(path, selector, set_=injected, replace_body=replace_body, append=append, force=force)

    monkeypatch.setattr(entries, "crud_update", fake)
    r = entries.entry_update_handler(
        str(f), "$1/HOF:handoff", set_="a:2", ctx=arqux_env.gov_ctx
    )
    assert r.profile == OUT_ERROR, r.to_text()
    assert f.read_bytes() == original, "rollback not CRLF-faithful"


# --- Round-3 (N12, N13): idempotent re-send / marker-set invariant ----------


def _open_markers(arqux_env, bp_id: str) -> set[str]:
    text = _bp_file(arqux_env, bp_id).read_text(encoding="utf-8")
    return set(re.findall(r"<!--\s*BLP:([\w.]+)\s*-->", text))


def test_blueprint_update_idempotent_resend_safe(arqux_env) -> None:
    proj, bp = arqux_env.proj_root, arqux_env.bp_id
    update_blueprint(bp, section="6", content="**Dentro:** x", path=str(proj), ctx=arqux_env.gov_ctx)
    before = _open_markers(arqux_env, bp)

    # Same content again — Updater no-op must NOT fall through to a header sweep.
    r = update_blueprint(bp, section="6", content="**Dentro:** x", path=str(proj), ctx=arqux_env.gov_ctx)
    assert "blueprint.update ok" in r.to_text(), r.to_text()

    assert _open_markers(arqux_env, bp) == before, "marker set changed on idempotent re-send"


def test_blueprint_update_requires_marker_pair(arqux_env) -> None:
    proj = arqux_env.proj_root
    d = proj / ".arqux" / "cycles" / arqux_env.cycle_id / "blueprints"
    d.mkdir(parents=True, exist_ok=True)
    (d / "BLP-040.md").write_text(
        '---\nblueprint_id: "BLP-040"\ntitle: "T"\ncycle: "' + arqux_env.cycle_id
        + '"\nstatus: "draft"\n---\n\n# BLP-040: T\n\n## §7: Reglas\n\nold\n',
        encoding="utf-8",
    )
    r = update_blueprint(
        "BLP-040", section="7", content="new", path=str(proj), ctx=arqux_env.gov_ctx
    )
    assert r.profile == OUT_ERROR, r.to_text()
    assert "NOT_FOUND" in r.to_text()


def test_blueprint_update_rejects_marker_space_before_colon(arqux_env) -> None:
    r = update_blueprint(
        arqux_env.bp_id, section="7", content="x <!-- BLP :7 --> y",
        path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
    )
    assert r.profile == OUT_ERROR, r.to_text()
