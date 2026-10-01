"""Tests for handler.how_to (BLP-012) — intent-based usage guides."""

from __future__ import annotations

from arqux.handlers.handler import _load_guides, how_to

_TOPICS = {
    "sesion_boot", "cambiar_identidad", "ciclo_blueprint",
    "tarea_blueprint_checkbox", "evidencia_pulse", "editar_skill_local",
    "checkpoint_wrk", "cerrar_sesion",
}


# ---------------------------------------------------------------------------
# Corpus sanity (AC-05)
# ---------------------------------------------------------------------------


def test_corpus_loads_all_8_guides() -> None:
    guides = _load_guides()
    topics = {g["topic"] for g in guides}
    assert topics == _TOPICS


def test_guides_have_steps_example_handlers() -> None:
    for g in _load_guides():
        assert g.get("steps"), g["topic"]
        assert g.get("example"), g["topic"]
        assert g.get("handlers"), g["topic"]


# ---------------------------------------------------------------------------
# AC-03 — intent guides with usable handler references
# ---------------------------------------------------------------------------


def test_identity_intent_returns_identity_switch_guide() -> None:
    out = how_to("cambiar de identidad")
    assert out.profile == "OUT-WORK"
    assert out.fields["topic"] == "cambiar_identidad"
    assert "identity.switch" in out.fields["guide"]
    assert "identity.switch" in out.fields["example"]


def test_alias_matches() -> None:
    assert how_to("blueprint").fields.get("topic") == "ciclo_blueprint"
    assert how_to("checkpoint").fields.get("topic") == "checkpoint_wrk"
    assert how_to("editar skill").fields.get("topic") == "editar_skill_local"


# ---------------------------------------------------------------------------
# AC-04 — no-match is actionable
# ---------------------------------------------------------------------------


def test_no_match_lists_topics_and_hints() -> None:
    out = how_to("desplegar a PyPI")
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("code") == "GUIDE_NOT_FOUND"
    assert set(out.fields.get("available_topics", [])) == _TOPICS
    assert "handler.list" in out.fields.get("hint", "")


def test_missing_intent_invalid_args() -> None:
    out = how_to()
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("code") == "INVALID_ARGS"


# ---------------------------------------------------------------------------
# AC-07 — content CORTEX override
# ---------------------------------------------------------------------------


def test_content_cortex_overrides_intent() -> None:
    out = how_to(content='intent:"cambiar de identidad"')
    assert out.fields.get("topic") == "cambiar_identidad"
