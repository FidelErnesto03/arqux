"""Local PlantUML server for Arqux HCORTEX document rendering.

Starts a local HTTP server that renders PlantUML diagrams on demand.
Compatible with kroki.io API so any markdown previewer can use it.

Usage:
    python -m arqux.plantuml_server           # start server on :9876
    arqux serve-plamtuml                       # same via CLI

Configuration for markdown previewers:
    markdown-preview-enhanced.plantumlServer: http://localhost:9876/plantuml/svg
    Or add to VSCode settings: \"markdown-preview-enhanced.plantumlServer\": \"http://localhost:9876/plantuml/svg\"
"""

from __future__ import annotations

import base64
import http.server
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from .plantuml import _find_jar, _BIN_DIR, setup_plantuml


class PlantUMLHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that renders PlantUML diagrams via kroki-compatible API."""

    jar_path: Path | None = None

    def do_GET(self) -> None:
        # Health check
        if self.path == "/" or self.path == "/health":
            self._json({"status": "ok", "server": "Arqux PlantUML Server"})
            return

        # kroki.io compatible: GET /plantuml/svg/encoded_puml
        if self.path.startswith("/plantuml/"):
            self._handle_kroki()
            return

        self.send_error(404, "Not found. Use /plantuml/<format>/<encoded> or /health")

    def _handle_kroki(self) -> None:
        """Handle kroki.io compatible PlantUML requests."""
        parts = self.path.split("/")
        # /plantuml/svg/encoded_text
        if len(parts) < 4:
            self.send_error(400, "Invalid path")
            return

        fmt = parts[2]  # svg or png
        encoded = parts[3]  # base64-encoded PUML

        try:
            # Decode the PUML source
            decoded = base64.urlsafe_b64decode(encoded + "==").decode("utf-8")
        except Exception:
            self.send_error(400, "Invalid base64 encoding")
            return

        if not Jar or not Java:
            self.send_error(500, "plantuml.jar or Java not available. Run: arqux setup-plantuml")
            return

        ok, result = _render(decoded, fmt)
        if ok:
            content_type = "image/svg+xml" if fmt == "svg" else "image/png"
            if isinstance(result, str):
                result = result.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)
        else:
            self._json({"error": result}, 500)

    def _json(self, data: dict, status: int = 200) -> None:
        import json

        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        pass  # Suppress request logging


Jar: Path | None = None
Java: str | None = None


def _render(source: str, fmt: str) -> tuple[bool, bytes | str]:
    """Render PUML to bytes."""
    import subprocess
    import tempfile

    puml_file = Path(tempfile.mktemp(suffix=".puml"))
    out_dir = Path(tempfile.mkdtemp())
    puml_file.write_text(f"@startuml\n{source}\n@enduml", encoding="utf-8")

    cmd = [Java, "-jar", str(Jar), f"-t{fmt}", "-charset", "UTF-8", "-output", str(out_dir), str(puml_file)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=30)
        out_files = list(out_dir.glob(f"*.{fmt}"))
        if r.returncode == 0 and out_files:
            return True, out_files[0].read_bytes()
        return False, r.stderr.decode("utf-8", errors="replace")[:300]
    except Exception as e:
        return False, str(e)
    finally:
        import shutil
        try:
            shutil.rmtree(out_dir, ignore_errors=True)
        except Exception:
            pass
        try:
            puml_file.unlink()
        except Exception:
            pass


def start_server(port: int = 9876, setup: bool = True) -> http.server.HTTPServer:
    """Start the PlantUML rendering server.

    Args:
        port: Port to listen on.
        setup: If True, auto-download plantuml.jar if missing.

    Returns:
        The running HTTPServer instance.
    """
    global Jar, Java
    import shutil

    Java = shutil.which("java")
    if not Java:
        print("ERROR: Java not found. Install JRE 8+.", file=sys.stderr)
        print("  sudo apt install default-jre", file=sys.stderr)
        sys.exit(1)

    Jar = _find_jar()
    if not Jar and setup:
        ok, msg = setup_plantuml()
        if ok:
            Jar = _BIN_DIR / "plantuml.jar"
        else:
            print(f"ERROR: {msg}", file=sys.stderr)
            print("Download manually: https://plantuml.com/download", file=sys.stderr)
            sys.exit(1)

    if not Jar:
        print("ERROR: plantuml.jar not found.", file=sys.stderr)
        sys.exit(1)

    PlantUMLHandler.jar_path = Jar
    server = http.server.HTTPServer(("0.0.0.0", port), PlantUMLHandler)

    print(f"[Arqux PlantUML Server] Running on http://localhost:{port}")
    print(f"  Health:    http://localhost:{port}/health")
    print(f"  Render:    http://localhost:{port}/plantuml/svg/<encoded>")
    print(f"  Configure: markdown-preview-enhanced.plantumlServer: http://localhost:{port}/plantuml/svg")
    print()
    print("Press Ctrl+C to stop.")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return server


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Arqux PlantUML Server")
    p.add_argument("--port", type=int, default=9876)
    p.add_argument("--no-setup", action="store_true", help="Skip plantuml.jar auto-download")
    args = p.parse_args()

    srv = start_server(port=args.port, setup=not args.no_setup)
    try:
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down.")
        srv.shutdown()
