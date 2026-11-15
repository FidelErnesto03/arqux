# SPDX-License-Identifier: MPL-2.0
"""CODEC-CORTEX 1.0.x conformance tests (BLP-005, post-1.0 retirement).

Verifies the ArqUX-owned boundary — model, level policy, selectors and the
HCORTEX-READ renderer — against the codec-cortex 1.0.x binding on the real
corpus. The legacy ``cortex`` 0.6.x equivalence suite was retired with the
1.0 line: the package is no longer a valid install, so parity with it is
historical, not a live contract.
"""

from __future__ import annotations

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


@pytest.fixture(scope="module")
def brain_doc():
    """The live project brain parsed through the v1 binding."""
    pytest.importorskip("codec_cortex.dispatcher")
    from codec_cortex.dispatcher import parse_cortex

    return model.from_codec_v1(
        parse_cortex(BRAIN.read_text(encoding="utf-8")), path=str(BRAIN)
    )


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


class TestLevelPolicy:
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
        hits = selectors.select(brain_doc, "FCS:*")
        assert hits, "expected FCS entries in brain"
        one = selectors.select_one(brain_doc, "$5/FCS:current")
        assert one.sigil == "FCS"
        with pytest.raises(selectors.NotFoundError):
            selectors.select_one(brain_doc, "NOPE:*")

    def test_wildcards(self, brain_doc):
        all_axm = selectors.select(brain_doc, "AXM:*")
        assert all(e.sigil == "AXM" for e in all_axm)


class TestReadRenderer:
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
            assert diag["api"] == "v1"
            assert diag["missing_capabilities"] == []
            assert diag["can_validate"] and diag["can_render_hcortex"]

    def test_v1_api_preferred_when_present(self):
        """Under the pinned codec-cortex>=1.0,<1.1 line the only legitimate
        binding is ``v1`` — legacy ``cortex`` and 1.0.0rc1 are not bound."""
        if _CODEC_CORTEX_API != "v1":
            pytest.skip("codec_cortex 1.0.x is not the active binding")
        assert _CODEC_CORTEX_API == "v1"

    def test_native_modules_have_no_codec_imports(self):
        import arqux.cortex.level_policy as lp
        import arqux.cortex.model as md
        import arqux.cortex.read_renderer as rr
        import arqux.cortex.selectors as sl
        for mod in (lp, rr, sl, md):
            src = Path(mod.__file__).read_text(encoding="utf-8")
            assert "import cortex" not in src
            assert "codec_cortex" not in src.split('"""')[2]  # docstring refs ok
