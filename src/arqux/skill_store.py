"""Skill trazability — OriginalStore, AdaptedStore, SkillRepository (BLP-040).

Implements the procedural line of BLP-038's three-lines architecture:

    OriginalStore  → skills/originals/   (immutable, third-party upstream)
    AdaptedStore   → skills/             (local adaptations, read/write)
    SkillRepository → resolves by priority: Adapted > Original > Native

The sigil ``STP`` is enriched with provenance metadata in ARQX:artifact:
    kind              : native | inherited | adapted
    source            : URL/path of the upstream (for inherited)
    upstream_version  : version tag of the upstream (for inherited)

Architectural blocking rules (BLP-040 §16):
    - Agents MUST NOT mutate files in ``skills/originals/``. The only way
      to modify an inherited skill is via ``AdaptedStore.save()`` which
      creates a fork in ``skills/``.
    - Components MUST NOT load skills directly from the filesystem. They
      must use ``SkillRepository.resolve(name)``.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .constants import (
    ArtifactKind,
    ArtifactMetadata,
    ArtifactUsage,
    CortexLevel,
    W005_MISSING_ORIGINAL_REF,
)
from .formats import (
    CortexArtifact,
    _ARQUX_GLOSSARY_TEXT,
    read_cortex_artifact,
    render_arqux_section,
)
from .migrator import migrate_skill_file

logger = logging.getLogger(__name__)


# --- Exceptions -------------------------------------------------------------

class SkillNotFoundError(Exception):
    """Raised when a skill cannot be resolved in any store."""

class SkillImportError(Exception):
    """Raised when a skill import fails."""


# --- Data classes -----------------------------------------------------------

@dataclass(frozen=True)
class STPDeclaration:
    """Provenance declaration for a skill artifact (BLP-040 §8)."""
    level: int = 2
    name: str = ""
    usage: str = "skill"
    kind: str = "native"  # native | inherited | adapted
    source: Optional[str] = None
    upstream_version: Optional[str] = None

    def to_metadata(self) -> ArtifactMetadata:
        return ArtifactMetadata(
            level=CortexLevel.from_int(self.level),
            name=self.name,
            usage=ArtifactUsage.from_str(self.usage),
            kind=ArtifactKind.from_str(self.kind),
            source=self.source,
            upstream_version=self.upstream_version,
        )


@dataclass
class SkillContract:
    """A resolved skill with its declaration and content (BLP-040 §8)."""
    declaration: STPDeclaration
    content: str
    path: Path
    original_ref: Optional[str] = None  # set for adapted skills
    warnings: list[str] = field(default_factory=list)

    @property
    def kind(self) -> str:
        return self.declaration.kind


# --- OriginalStore (immutable upstream) -------------------------------------

class OriginalStore:
    """Read-only store for upstream skill artifacts (BLP-040 §8).

    Files live at ``<arqux_root>/skills/originals/<name>.skill.md``.
    They are IMMUTABLE: ``save()`` is only used at import time to capture
    the upstream snapshot. After that, no agent may modify them.
    """

    BASE_DIR_NAME: str = "skills/originals"

    def __init__(self, arqux_root: Path | str) -> None:
        self.arqux_root = Path(arqux_root)
        self.base_path = self.arqux_root / self.BASE_DIR_NAME

    def save(
        self,
        name: str,
        content: str,
        declaration: STPDeclaration,
    ) -> Path:
        """Persist an upstream skill snapshot (import-time only).

        Returns the path where the original was saved.
        """
        self.base_path.mkdir(parents=True, exist_ok=True)
        path = self.base_path / f"{name}.skill.md"
        # Compose CORTEX document: $0 glossary + $0.1 arqux metadata + content.
        arqux_section = render_arqux_section(declaration.to_metadata())
        full_content = f"$0\n\n{_ARQUX_GLOSSARY_TEXT}\n{arqux_section}\n\n{content}\n"
        path.write_text(full_content, encoding="utf-8")
        logger.info("OriginalStore.save: %s", path)
        return path

    def get(self, name: str) -> SkillContract:
        """Return the immutable skill contract for ``name``."""
        path = self.base_path / f"{name}.skill.md"
        if not path.exists():
            raise SkillNotFoundError(f"Original skill not found: {path}")
        artifact = read_cortex_artifact(path)
        return SkillContract(
            declaration=STPDeclaration(
                level=artifact.metadata.level.value,
                name=artifact.metadata.name,
                usage=artifact.metadata.usage.value,
                kind=artifact.metadata.kind.value,
                source=artifact.metadata.source,
                upstream_version=artifact.metadata.upstream_version,
            ),
            content=artifact.payload,
            path=path,
        )

    def exists(self, name: str) -> bool:
        return (self.base_path / f"{name}.skill.md").exists()

    def list(self) -> list[str]:
        if not self.base_path.exists():
            return []
        names: list[str] = []
        for p in self.base_path.glob("*.skill.md"):
            # p.stem for "a.skill.md" returns "a.skill" — strip the .skill suffix.
            stem = p.name[:-len(".skill.md")] if p.name.endswith(".skill.md") else p.stem
            names.append(stem)
        return sorted(names)


# --- AdaptedStore (local fork, read/write) ----------------------------------

class AdaptedStore:
    """Read/write store for locally adapted skills (BLP-040 §8).

    Files live at ``<arqux_root>/skills/<name>.skill.md``. They take
    PRIORITY over OriginalStore entries during resolution.
    """

    BASE_DIR_NAME: str = "skills"

    def __init__(self, arqux_root: Path | str) -> None:
        self.arqux_root = Path(arqux_root)
        self.base_path = self.arqux_root / self.BASE_DIR_NAME

    def save(
        self,
        name: str,
        content: str,
        original_ref: Optional[str] = None,
        *,
        declaration: Optional[STPDeclaration] = None,
    ) -> Path:
        """Persist an adapted (or native) skill.

        If ``original_ref`` is provided and ``declaration`` is None, the
        declaration is constructed as ``kind=adapted`` with the original_ref
        as source. If both are None, the skill is treated as native.
        """
        self.base_path.mkdir(parents=True, exist_ok=True)
        path = self.base_path / f"{name}.skill.md"

        if declaration is None:
            if original_ref:
                declaration = STPDeclaration(
                    name=name,
                    kind="adapted",
                    source=original_ref,
                )
            else:
                declaration = STPDeclaration(name=name, kind="native")

        arqux_section = render_arqux_section(declaration.to_metadata())
        full_content = f"$0\n\n{_ARQUX_GLOSSARY_TEXT}\n{arqux_section}\n\n{content}\n"
        path.write_text(full_content, encoding="utf-8")
        logger.info("AdaptedStore.save: %s (kind=%s)", path, declaration.kind)
        return path

    def get(self, name: str) -> SkillContract:
        path = self.base_path / f"{name}.skill.md"
        if not path.exists():
            raise SkillNotFoundError(f"Adapted skill not found: {path}")
        artifact = read_cortex_artifact(path)
        raw = path.read_text(encoding="utf-8")
        # Strip ARQX preamble ($0 glossary + $0.1 metadata) to extract
        # the actual skill body: everything after the metadata block.
        # Format: $0\n\nGLOSSARY\n$19: ARQUX METADATA\n\nARQX:artifact{...}\n\nBODY
        parts = raw.split("ARQX:artifact")[-1] if "ARQX:artifact" in raw else ""
        body_parts = parts.split("\n\n", 1) if parts else []
        skill_body = body_parts[-1].strip() if body_parts else raw.strip()
        contract = SkillContract(
            declaration=STPDeclaration(
                level=artifact.metadata.level.value,
                name=artifact.metadata.name,
                usage=artifact.metadata.usage.value,
                kind=artifact.metadata.kind.value,
                source=artifact.metadata.source,
                upstream_version=artifact.metadata.upstream_version,
            ),
            content=skill_body,
            path=path,
            original_ref=artifact.metadata.source,
        )
        # BLP-040 §13 edge case: adapted skill without original_ref → W005.
        if (contract.declaration.kind == "adapted"
                and not contract.original_ref):
            contract.warnings.append(W005_MISSING_ORIGINAL_REF)
        return contract

    def exists(self, name: str) -> bool:
        return (self.base_path / f"{name}.skill.md").exists()

    def list(self) -> list[str]:
        if not self.base_path.exists():
            return []
        names: list[str] = []
        for p in self.base_path.glob("*.skill.md"):
            # p.stem for "a.skill.md" returns "a.skill" — strip the .skill suffix.
            stem = p.name[:-len(".skill.md")] if p.name.endswith(".skill.md") else p.stem
            names.append(stem)
        return sorted(names)


# --- SkillRepository (resolution with priority) -----------------------------

class SkillRepository:
    """Resolves skills by priority: Adapted > Original > Native (BLP-040 §8).

    Usage::

        repo = SkillRepository(arqux_root)
        contract = repo.resolve("owasp-top10")
        print(contract.kind)  # adapted | inherited | native
    """

    def __init__(self, arqux_root: Path | str) -> None:
        self.arqux_root = Path(arqux_root)
        self.adapted = AdaptedStore(self.arqux_root)
        self.original = OriginalStore(self.arqux_root)

    def resolve(self, name: str) -> SkillContract:
        """Resolve a skill by priority: Adapted → Original → Native.

        Raises ``SkillNotFoundError`` if the skill doesn't exist in any
        store AND cannot be resolved as a packaged native skill.
        """
        # 1. AdaptedStore (highest priority).
        if self.adapted.exists(name):
            return self.adapted.get(name)
        # 2. OriginalStore.
        if self.original.exists(name):
            return self.original.get(name)
        # 3. Native: packaged .skill.md files shipped with ArqUX.
        native_path = self._resolve_native(name)
        if native_path is not None:
            artifact = read_cortex_artifact(native_path)
            return SkillContract(
                declaration=STPDeclaration(
                    level=artifact.metadata.level.value,
                    name=artifact.metadata.name,
                    usage=artifact.metadata.usage.value,
                    kind=artifact.metadata.kind.value,
                ),
                content=artifact.payload,
                path=native_path,
            )
        raise SkillNotFoundError(
            f"Skill {name!r} not found in AdaptedStore, OriginalStore, "
            f"or packaged natives."
        )

    def list_all(self) -> list[dict[str, str]]:
        """List all skills across stores with their kind."""
        seen: dict[str, dict[str, str]] = {}
        for name in self.adapted.list():
            try:
                contract = self.adapted.get(name)
                seen[name] = {
                    "name": name,
                    "kind": contract.declaration.kind,
                    "store": "adapted",
                    "path": str(contract.path),
                }
            except Exception:  # noqa: BLE001
                continue
        for name in self.original.list():
            if name in seen:
                continue
            try:
                contract = self.original.get(name)
                seen[name] = {
                    "name": name,
                    "kind": contract.declaration.kind,
                    "store": "original",
                    "path": str(contract.path),
                }
            except Exception:  # noqa: BLE001
                continue
        # Native skills (packaged).
        for name in self._list_native():
            if name in seen:
                continue
            seen[name] = {
                "name": name,
                "kind": "native",
                "store": "packaged",
                "path": str(self._resolve_native(name) or ""),
            }
        return sorted(seen.values(), key=lambda d: d["name"])

    def import_skill(
        self,
        source: str,
        name: str,
        content: str,
        *,
        upstream_version: Optional[str] = None,
    ) -> dict[str, Any]:
        """Import a third-party skill (BLP-040 T-040.5).

        Preserves the original in ``skills/originals/`` and creates an
        initial adapted copy in ``skills/``.
        """
        decl = STPDeclaration(
            name=name,
            kind="inherited",
            source=source,
            upstream_version=upstream_version,
        )
        # Save the immutable original first.
        original_path = self.original.save(name, content, decl)
        # Then create an adapted copy (initially identical content).
        adapted_path = self.adapted.save(
            name, content, original_ref=str(original_path), declaration=decl,
        )
        logger.info(
            "SkillRepository.import_skill: imported %s from %s "
            "(original=%s, adapted=%s)",
            name, source, original_path, adapted_path,
        )
        return {
            "name": name,
            "source": source,
            "upstream_version": upstream_version,
            "original_path": str(original_path),
            "adapted_path": str(adapted_path),
            "kind": "inherited",
        }

    # --- Internals ---

    def _resolve_native(self, name: str) -> Optional[Path]:
        """Resolve a packaged native .skill.md by name.

        Looks in ``arqux/skills/<name>.skill.md`` (the framework's bundled
        skill files).
        """
        from .constants import PACKAGE_ROOT
        candidates = [
            PACKAGE_ROOT / "skills" / f"{name}.skill.md",
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def _list_native(self) -> list[str]:
        from .constants import PACKAGE_ROOT
        native_dir = PACKAGE_ROOT / "skills"
        if not native_dir.exists():
            return []
        names: list[str] = []
        for p in native_dir.glob("*.skill.md"):
            stem = p.name[:-len(".skill.md")] if p.name.endswith(".skill.md") else p.stem
            names.append(stem)
        return sorted(names)
