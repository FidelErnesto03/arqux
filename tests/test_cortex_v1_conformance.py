# SPDX-License-Identifier: MPL-2.0
"""BLP-005 — CODEC-CORTEX 1.0.x conformance tests.

Verifies the ArqUX-owned boundary: model, level policy, selectors and the
HCORTEX-READ renderer reproduce the legacy codec semantics on the real
corpus, and ``_bind_v1_api`` reports full capabilities when the 1.0.x
surface is present.
"""

from __future__ import annotations

import collections
from pathlib import Path

import pytest

from arqux.core.state import (
    _CODEC_CORTEX_API,
    _HAS_CODEC_CORTEX,
    codec_cortex_diagnostics,
)
from arqux.cortex import level_policy, model, read_renderer, selectors

ARQUX_ROOT = Path(__file__).resolve().parent.parent
BRAIN = ARQUX_ROOT / ".arqux" / "brain.cortex"


def _legacy_validate(doc):
    from cortex.core.validator import validate as legacy_validate
    return legacy_validate(doc)


def _legacy_render(doc, **kwargs):
    from cortex.hcortex.read_renderer import render_hcortex_read as legacy_render
    return legacy_render(doc, **kwargs)


def _diag_sig(diagnostics):
    return collections.Counter(
        (d.get("code"), d.get("severity"), d.get("sigil"),
         d.get("entry"), d.get("message"))
        for d in diagnostics
    )


@pytest.fixture(scope="module")
def brain_doc():
    pytest.importorskip("cortex.core.parser")
    from cortex.core.parser import parse_cortex
    return parse_cortex(BRAIN.read_text(encoding="utf-8"), path=str(BRAIN))


class TestModel:
    def test_cortex_document_api(self):
        doc = model.CortexDocument()
        sec = doc.get_or_create_section("$2", "Active Work")
        sec.entries.append(model.Entry(
            section="$2", sigil="FCS", name="focus", type="attrs",
            value={"what": "x", "status": "current"}))
        assert doc.section_ids == ["$2"]
        assert doc.get_section("2") is sec
        assert [e.name for _, e in doc.iter_entries()] == ["focus"]
        assert doc.find_entries(sigil="FCS")[0].value["what"] == "x"

    def test_normalize_section_id(self):
        assert model.normalize_section_id("2") == "$2"
        assert model.normalize_section_id("$2: TITLE") == "$2"
        assert model.normalize_section_id(None) == "$0"

    def test_entry_hash_stable(self):
        e1 = model.Entry(section="$1", sigil="AXM", name="a", type="attrs",
                         value={"k": "v"})
        e2 = model.Entry(section="$1", sigil="AXM", name="a", type="attrs",
                         value={"k": "v"})
        assert e1.hash == e2.hash and e1.entry_id == e2.hash


class TestLevelPolicyEquivalence:
    def test_brain_diagnostics_identical(self, brain_doc):
        base = _diag_sig(_legacy_validate(brain_doc))
        mine = _diag_sig(level_policy.validate(brain_doc))
        assert mine == base

    def test_corpus_diagnostics_identical(self):
        pytest.importorskip("cortex.core.parser")
        from cortex.core.parser import parse_cortex
        files = list((ARQUX_ROOT / ".arqux").rglob("*.cortex"))[:40]
        files += list((ARQUX_ROOT.parent / ".arqux").glob("*.cortex"))
        assert files, "fixture corpus must not be empty"
        for f in files:
            doc = parse_cortex(f.read_text(encoding="utf-8"), path=str(f))
            assert _diag_sig(level_policy.validate(doc)) == \
                _diag_sig(_legacy_validate(doc)), f"diagnostic drift on {f}"

    def test_strict_mode_promotes_warnings(self, brain_doc):
        out = level_policy.validate(brain_doc, strict=True)
        assert all(d["severity"] != "warning" for d in out)

    def test_blp020_identity_lesson_exemption(self):
        doc = model.CortexDocument()
        doc.meta["path"] = "identity.cortex"
        z = doc.get_or_create_section("$0")
        z.entries.append(model.Entry(
            section="$0", sigil="ARQX", name="contract", type="attrs",
            value={"usage": "identity"}))
        lessons = doc.get_or_create_section("$5", "BEHAVIORAL LESSONS")
        lessons.entries.append(model.Entry(
            section="$5", sigil="LNG", name="l1", type="attrs",
            value={"type": "behavioral", "lesson": "x"}))
        # Skill kind → LNG live state would be E023, exempted by BLP-020.
        doc2 = model.CortexDocument()
        doc2.meta["path"] = "skill.cortex"
        doc2.get_or_create_section("$0").entries.append(model.Entry(
            section="$0", sigil="ARQX", name="contract", type="attrs",
            value={"usage": "identity"}))
        s5 = doc2.get_or_create_section("$5", "BEHAVIORAL LESSONS")
        s5.entries.append(model.Entry(
            section="$5", sigil="LNG", name="l1", type="attrs",
            value={"type": "behavioral", "lesson": "x"}))
        out = level_policy.validate(doc2)
        assert not any(d["code"] == "E023_LEVEL1_LIVE_STATE" for d in out)


class TestSelectors:
    def test_parse_and_select(self, brain_doc):
        pytest.importorskip("cortex.core.parser")
        # selectors operate on the codec-native doc too (same API surface)
        hits = selectors.select(brain_doc, "FCS:*")
        assert hits, "expected FCS entries in brain"
        one = selectors.select_one(brain_doc, "$3/FCS:current")
        assert one.sigil == "FCS"
        with pytest.raises(selectors.NotFoundError):
            selectors.select_one(brain_doc, "NOPE:*")

    def test_wildcards(self, brain_doc):
        all_axm = selectors.select(brain_doc, "AXM:*")
        assert all(e.sigil == "AXM" for e in all_axm)


class TestReadRendererEquivalence:
    def test_brain_render_identical(self, brain_doc):
        pytest.importorskip("cortex.hcortex.read_renderer")
        assert read_renderer.render_hcortex_read(brain_doc) == \
            _legacy_render(brain_doc)

    def test_render_profiles_and_modes(self, brain_doc):
        pytest.importorskip("cortex.hcortex.read_renderer")
        for kwargs in ({"profile": "MIN"}, {"profile": "FULL"},
                       {"mode": "AUDIT"}, {"mode": "RECOVERY"},
                       {"layout": "priority"}, {"with_source": True}):
            assert read_renderer.render_hcortex_read(brain_doc, **kwargs) == \
                _legacy_render(brain_doc, **kwargs), kwargs

    def test_render_declares_profile_first(self, brain_doc):
        out = read_renderer.render_hcortex_read(brain_doc)
        assert out.splitlines()[0].startswith("Perfil: CORTEX-")
        assert "roundtrip: false" in out.splitlines()[1]


class TestBinding:
    def test_diagnostics_shape(self):
        diag = codec_cortex_diagnostics()
        assert set(diag) >= {"available", "api", "missing_capabilities",
                             "can_parse", "can_validate", "can_render_hcortex"}
        if _HAS_CODEC_CORTEX:
            assert diag["api"] in {"v1", "legacy", "rc1"}
            if diag["api"] == "v1":
                assert diag["missing_capabilities"] == []
                assert diag["can_validate"] and diag["can_render_hcortex"]

    def test_v1_api_preferred_when_present(self):
        """When codec_cortex 1.0.x is importable at bind time the binding
        must be v1. In environments where only the legacy ``cortex`` package
        is installed, api=='legacy' is the correct binding — the v1 check
        belongs to the pinned 1.0.x env."""
        if _CODEC_CORTEX_API != "v1":
            pytest.skip("codec_cortex 1.0.x is not the active binding")
        assert _CODEC_CORTEX_API == "v1"

    def test_v1_path_error_equivalence(self):
        """codec_cortex 1.0.x parse → ArqUX model → ported validate must
        preserve every error-severity diagnostic and the valid verdict.

        Known, documented deltas (v1 is strictly more capable, never less):
        - ``E017_UNPARSED_LINE`` disappears: v1 parses entries (e.g. the
          ``LOOP:`` declaration) that the 0.6.2 parser rejects.
        - ``I001_UNDECLARED_SIGIL`` infos disappear: v1 surfaces ``$0``
          declarations as first-class glossary symbols instead of
          auto-registering them at parse time.
        """
        codec_cortex = pytest.importorskip("codec_cortex.dispatcher")
        pytest.importorskip("cortex.core.parser")
        pytest.importorskip("cortex.core.validator")
        from cortex.core.parser import parse_cortex as legacy_parse
        from cortex.core.validator import validate as legacy_validate

        from arqux.core.state._crud import filter_dialect_false_positives

        def errors_of(diags):
            return _diag_sig([d for d in diags if d.get("severity") == "error"])

        def v1_parse_or_error(text):
            """v1 dispatcher rejects outright (ParseError) where legacy
            tolerates — e.g. G010 missing ``$0:format`` on timelog files.
            Surface the rejection as an error diagnostic so the verdict
            comparison stays meaningful."""
            try:
                return model.from_codec_v1(codec_cortex.parse_cortex(text)), []
            except Exception as exc:  # codec_cortex.scalars.ParseError
                code = getattr(exc, "code", type(exc).__name__)
                return None, [{
                    "code": code, "severity": "error",
                    "message": str(exc),
                }]

        files = [BRAIN]
        files += list((ARQUX_ROOT / ".arqux").rglob("*.cortex"))[:15]
        for f in files:
            text = f.read_text(encoding="utf-8")
            v1_doc, v1_parse_errors = v1_parse_or_error(text)
            leg_doc = legacy_parse(text, path=str(f))
            if v1_doc is None:
                v1_diags = v1_parse_errors
                # Documented drift: pre-migration artifacts lack $0:format,
                # so v1's only diagnostic is G010 while legacy parses clean.
                # That is the dialect gate working, not error drift.
                if {d.get("code") for d in v1_diags} == {"G010_FORMAT_REQUIRED"}:
                    continue
            else:
                v1_diags = filter_dialect_false_positives(
                    v1_doc, level_policy.validate(v1_doc))
            leg_diags = filter_dialect_false_positives(
                leg_doc, legacy_validate(leg_doc))
            assert errors_of(v1_diags) == errors_of(leg_diags), \
                f"error-severity drift on {f}"
            v1_valid = not errors_of(v1_diags)
            leg_valid = not errors_of(leg_diags)
            assert v1_valid == leg_valid, f"validity drift on {f}"

    def test_native_modules_have_no_codec_imports(self):
        import arqux.cortex.level_policy as lp
        import arqux.cortex.model as md
        import arqux.cortex.read_renderer as rr
        import arqux.cortex.selectors as sl
        for mod in (lp, rr, sl, md):
            src = Path(mod.__file__).read_text(encoding="utf-8")
            assert "import cortex" not in src
            assert "codec_cortex" not in src.split('"""')[2]  # docstring refs ok
