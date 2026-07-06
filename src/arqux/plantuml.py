"""PlantUML integration for Arqux.

Renders PUML blocks from HCORTEX documents (BLP-NNN.md, MANIFEST.md) to
PNG/SVG images. Used by the Blueprint workflow for diagram validation
during cross-verification.

Requirements:
    Java runtime (java) + plantuml.jar in PATH or ~/.arqux/bin/plantuml.jar.
    Install: arqux setup-plantuml

Usage:
    from arqux.plantuml import render_puml, is_available

    if is_available():
        svg = render_puml(puml_source, format="svg")
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .constants import ARQUX_DIR


_PLANTUML_JAR = "plantuml.jar"
_BIN_DIR = Path.home() / ".arqux" / "bin"


def is_available() -> bool:
    """Check if PlantUML is available for rendering."""
    java = shutil.which("java")
    if not java:
        return False
    for candidate in (_BIN_DIR / _PLANTUML_JAR, Path("plantuml.jar")):
        if candidate.exists():
            return True
    return shutil.which("plantuml") is not None


def _find_jar() -> Path | None:
    """Find the plantuml.jar file."""
    for candidate in (_BIN_DIR / _PLANTUML_JAR, Path("plantuml.jar")):
        if candidate.exists():
            return candidate
    # Check if `plantuml` CLI is available
    cli = shutil.which("plantuml")
    if cli:
        return Path(cli)
    return None


def render_puml(puml_source: str, format: str = "svg", output_dir: Path | None = None) -> tuple[bool, str]:
    """Render a PUML source block to an image.

    Args:
        puml_source: The PUML source text (body of the @startuml/@enduml block).
        format: Output format ("svg" or "png").
        output_dir: Directory for output. Uses temp directory if not specified.

    Returns:
        (success: bool, output_path_or_error: str)
    """
    jar = _find_jar()
    if jar is None:
        return False, "plantuml.jar not found. Run: arqux setup-plantuml"

    java = shutil.which("java")
    if not java:
        return False, "java not found. Install a Java runtime (JRE 8+)."

    out_dir = output_dir or Path(tempfile.mkdtemp(prefix="arqux_puml_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write PUML source to temp file
    puml_file = out_dir / "diagram.puml"
    puml_file.write_text(f"@startuml\n{puml_source}\n@enduml", encoding="utf-8")

    # Run plantuml
    cmd = [java, "-jar", str(jar), f"-t{format}", "-output", str(out_dir), str(puml_file)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return False, f"PlantUML error: {result.stderr.strip()[:200]}"
        # Find the output file
        for f in out_dir.glob(f"diagram.{format}"):
            return True, str(f)
        return False, f"Output file not found. PlantUML output: {result.stdout.strip()[:200]}"
    except subprocess.TimeoutExpired:
        return False, "PlantUML rendering timed out (60s)"
    except Exception as e:
        return False, f"PlantUML error: {e}"


def render_blueprint_diagrams(blueprint_path: Path, output_dir: Path = None) -> dict[str, str]:
    """Extract and render all PUML diagrams from a Blueprint HCORTEX document.

    Args:
        blueprint_path: Path to BLP-NNN.md
        output_dir: Output directory for rendered images

    Returns:
        Dict mapping section names to rendered image paths.
    """
    import re

    if not blueprint_path.exists():
        return {}

    content = blueprint_path.read_text(encoding="utf-8")

    # Match: §N: TITLE followed by ```puml ... @startuml ... @enduml ... ```
    section_pattern = re.compile(
        r'## (§\d+:\s*[^\n]+)\n.*?```puml\s*\n(.*?@enduml.*?)```', re.DOTALL
    )
    results = {}
    out_dir = output_dir or blueprint_path.parent / "diagrams"
    out_dir.mkdir(parents=True, exist_ok=True)

    for m in section_pattern.finditer(content):
        section_title = m.group(1).strip().replace("§", "").replace(":", "_").replace(" ", "_")
        puml_body = m.group(2).strip()
        # Remove @startuml/@enduml wrappers if they exist
        puml_body = re.sub(r'@startuml.*?\n', '', puml_body)
        puml_body = re.sub(r'@enduml', '', puml_body)

        filename = f"{blueprint_path.stem}_{section_title}"
        ok, path = render_puml(puml_body, format="svg", output_dir=out_dir)
        if ok:
            results[section_title] = path

    return results


def setup_plantuml(force: bool = False) -> tuple[bool, str]:
    """Download and install plantuml.jar to ~/.arqux/bin/."""
    _BIN_DIR.mkdir(parents=True, exist_ok=True)
    jar_path = _BIN_DIR / _PLANTUML_JAR

    if jar_path.exists() and not force:
        return True, f"plantuml.jar already installed at {jar_path}"

    # Download plantuml.jar
    import urllib.request

    url = "https://github.com/plantuml/plantuml/releases/download/v1.2024.5/plantuml-1.2024.5.jar"
    try:
        print(f"Downloading plantuml.jar from {url}...")
        urllib.request.urlretrieve(url, str(jar_path))
        jar_path.chmod(0o755)
        return True, f"plantuml.jar installed at {jar_path}"
    except Exception as e:
        return False, f"Failed to download plantuml.jar: {e}. Please install manually from https://plantuml.com/download"
