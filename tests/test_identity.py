"""Tests for IdentityManager — agent identity resolution (BLP-039)."""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.constants import (
    ARQUX_DIR,
    CortexLevel,
)
from arqux.formats import CortexArtifact
from arqux.identity import (
    DEFAULT_AGENT,
    KNOWN_AGENTS,
    IdentityManager,
    IdentityNotFoundError,
    InvalidContractTypeError,
    SessionContext,
    _extract_contracts,
)

# --- Fixtures ---------------------------------------------------------------

@pytest.fixture
def identities_dir(tmp_path: Path) -> Path:
    """Create a fake identities dir with jarvis.cortex and alfred.cortex."""
    d = tmp_path / ARQUX_DIR / "identities"
    d.mkdir(parents=True)

    (d / "jarvis.cortex").write_text(
        "# §0 METADATA{\n"
        "#   level: 1,\n"
        '#   name: "jarvis",\n'
        '#   usage: "identity",\n'
        '#   kind: "native",\n'
        '#   agent: "jarvis"\n'
        "# }\n\n"
        "$0\nGSIG:IDN:identity|attrs|B|Semantic|Actor identity\n"
        "GSIG:AXM:axiom|attrs|H|Prefrontal|Stable behavioural axiom\n\n"
        "$1: IDENTITY\n"
        'IDN:jarvis{agent:"jarvis", name:"jarvis"}\n\n'
        "$2: AXIOMS\n"
        'AXM:claim_and_execute{name:"claim_and_execute", status:"current", body:"Claim a single task and execute it"}\n'
        'AXM:architect_first{name:"architect_first", status:"current", body:"Always consult the architect"}\n\n'
        "$3: LIMITS\n"
        'LIM:single_task{name:"single_task", status:"current", body:"Only one task at a time"}\n',
        encoding="utf-8",
    )

    (d / "alfred.cortex").write_text(
        "# §0 METADATA{\n"
        "#   level: 1,\n"
        '#   name: "alfred",\n'
        '#   usage: "identity",\n'
        '#   kind: "native",\n'
        '#   agent: "alfred"\n'
        "# }\n\n"
        "$0\nGSIG:IDN:identity|attrs|B|Semantic|Actor identity\n\n"
        "$1: IDENTITY\n"
        'IDN:alfred{agent:"alfred", name:"alfred"}\n'
        "$2: AXIOMS\n"
        'AXM:standby_first{name:"standby_first", status:"current", body:"Wait for instructions"}\n',
        encoding="utf-8",
    )
    return d


@pytest.fixture
def manager(identities_dir: Path) -> IdentityManager:
    return IdentityManager(identities_dir=identities_dir)


# --- resolve() tests --------------------------------------------------------

class TestResolve:
    def test_resolves_existing_agent(self, manager: IdentityManager) -> None:
        art = manager.resolve("jarvis")
        assert isinstance(art, CortexArtifact)
        assert art.metadata.level is CortexLevel.BEHAVIORAL
        assert art.metadata.name == "jarvis"
        assert art.filename == "jarvis"

    def test_resolve_unknown_agent_raises(self, manager: IdentityManager) -> None:
        with pytest.raises(IdentityNotFoundError):
            manager.resolve("nonexistent")

    def test_resolve_empty_name_raises(self, manager: IdentityManager) -> None:
        with pytest.raises(IdentityNotFoundError):
            manager.resolve("")

    def test_resolve_alfred_default(self, manager: IdentityManager) -> None:
        art = manager.resolve(DEFAULT_AGENT)
        assert art.metadata.name == "alfred"


# --- bind_to_session() tests ------------------------------------------------

class TestBindToSession:
    def test_bind_returns_session_context(self, manager: IdentityManager) -> None:
        ctx = manager.bind_to_session("jarvis")
        assert isinstance(ctx, SessionContext)
        assert ctx.agent == "jarvis"
        assert isinstance(ctx.identity, CortexArtifact)
        # Contracts extracted from $2 AXIOMS + $3 LIMITS.
        axm_contracts = ctx.contracts_by_type("AXM")
        assert len(axm_contracts) >= 2
        assert any(c["name"] == "claim_and_execute" for c in axm_contracts)
        lim_contracts = ctx.contracts_by_type("LIM")
        assert len(lim_contracts) >= 1
        assert lim_contracts[0]["name"] == "single_task"

    def test_bind_unknown_agent_raises(self, manager: IdentityManager) -> None:
        with pytest.raises(IdentityNotFoundError):
            manager.bind_to_session("nonexistent")

    def test_bind_writes_to_context_cortex(
        self, manager: IdentityManager, identities_dir: Path,
    ) -> None:
        # Pre-create a context.cortex.
        ws_root = identities_dir.parent
        ctx_path = ws_root / "context.cortex"
        ctx_path.write_text(
            "$0\n\n$1: CURRENT\n"
            'CTX:old-agent project="test" scope="work" agent="old-agent"\n',
            encoding="utf-8",
        )
        manager.bind_to_session("jarvis")
        content = ctx_path.read_text(encoding="utf-8")
        assert 'agent="jarvis"' in content
        assert 'agent="old-agent"' not in content


# --- list_identities() tests ------------------------------------------------

class TestListIdentities:
    def test_lists_known_identities(self, manager: IdentityManager) -> None:
        names = manager.list_identities()
        assert "jarvis" in names
        assert "alfred" in names

    def test_excludes_lessons_files(self, manager: IdentityManager, identities_dir: Path) -> None:
        # Drop a fake lessons.cortex file (should be excluded from list).
        (identities_dir / "jarvis.lessons.cortex").write_text(
            "# §0 METADATA{\n#   level: 0\n# }\n$0\n", encoding="utf-8",
        )
        names = manager.list_identities()
        assert "jarvis.lessons" not in names
        assert "jarvis" in names


# --- elevate_to_identity() tests (BLP-038 integration) ---------------------

class TestElevateToIdentity:
    def test_elevate_axiom_injects_axm(self, manager: IdentityManager, identities_dir: Path) -> None:
        result = manager.elevate_to_identity(
            agent="jarvis",
            lesson_id="lsn-042",
            contract_type="AXIOM",
            pattern="Always use exponential backoff on external API calls",
            evidence_ref="T-037-04",
        )
        assert result["agent"] == "jarvis"
        assert result["sigil"] == "AXM"
        assert result["name"] == "lsn-042"
        assert result["written"] is True

        # Verify the AXM was actually written to the file.
        content = (identities_dir / "jarvis.cortex").read_text(encoding="utf-8")
        assert "AXM:lsn-042{" in content
        assert "exponential backoff" in content
        assert 'source_lesson:"lsn-042"' in content
        assert 'evidence_ref:"T-037-04"' in content

    def test_elevate_limit_injects_lim(self, manager: IdentityManager, identities_dir: Path) -> None:
        manager.elevate_to_identity(
            agent="jarvis",
            lesson_id="lsn-043",
            contract_type="LIMIT",
            pattern="Never modify brain.cortex without sync_brain",
        )
        content = (identities_dir / "jarvis.cortex").read_text(encoding="utf-8")
        assert "LIM:lsn-043{" in content
        assert "sync_brain" in content

    def test_elevate_invalid_contract_raises(self, manager: IdentityManager) -> None:
        with pytest.raises(InvalidContractTypeError):
            manager.elevate_to_identity(
                agent="jarvis", lesson_id="lsn-001", contract_type="KNW",
            )

    def test_elevate_unknown_agent_raises(self, manager: IdentityManager) -> None:
        with pytest.raises(IdentityNotFoundError):
            manager.elevate_to_identity(
                agent="nonexistent", lesson_id="lsn-001", contract_type="AXIOM",
            )

    def test_elevate_empty_agent_raises(self, manager: IdentityManager) -> None:
        with pytest.raises(IdentityNotFoundError):
            manager.elevate_to_identity(
                agent="", lesson_id="lsn-001", contract_type="AXIOM",
            )

    def test_elevate_creates_section_if_missing(
        self, manager: IdentityManager, identities_dir: Path,
    ) -> None:
        # alfred.cortex has $2 AXIOMS but no $3 LIMITS. Elevate a LIMIT —
        # the manager should create the section.
        manager.elevate_to_identity(
            agent="alfred",
            lesson_id="lsn-050",
            contract_type="LIMIT",
            pattern="Always confirm before commits",
        )
        content = (identities_dir / "alfred.cortex").read_text(encoding="utf-8")
        assert "LIM:lsn-050{" in content
        # Section $3 LIMITS should now exist.
        assert "$3: LIMITS" in content or "$3:" in content


# --- Contract extraction tests ---------------------------------------------

class TestExtractContracts:
    def test_extracts_axm_and_lim(self) -> None:
        payload = (
            "$2: AXIOMS\n"
            'AXM:first{name:"first", status:"current", body:"b1"}\n'
            'AXM:second{name:"second", status:"current", body:"b2"}\n\n'
            "$3: LIMITS\n"
            'LIM:only{name:"only", status:"current", body:"l1"}\n'
        )
        contracts = _extract_contracts(payload)
        axm = [c for c in contracts if c["sigil"] == "AXM"]
        lim = [c for c in contracts if c["sigil"] == "LIM"]
        assert len(axm) == 2
        assert len(lim) == 1

    def test_strips_metadata_block(self) -> None:
        payload = (
            "# §0 METADATA{\n"
            "#   level: 1,\n"
            '#   name: "x",\n'
            '#   usage: "identity",\n'
            '#   kind: "native"\n'
            "# }\n\n"
            "$2: AXIOMS\n"
            'AXM:a{name:"a", body:"b"}\n'
        )
        contracts = _extract_contracts(payload)
        assert len(contracts) == 1
        assert contracts[0]["name"] == "a"


# --- Known agents sanity check ---------------------------------------------

class TestKnownAgents:
    def test_known_agents_includes_canonical_four(self) -> None:
        # BLP-035 §17 lists 4 core identity files.
        for name in ("alfred", "jarvis", "seshat", "heimdall"):
            assert name in KNOWN_AGENTS

    def test_default_agent_is_alfred(self) -> None:
        assert DEFAULT_AGENT == "alfred"
