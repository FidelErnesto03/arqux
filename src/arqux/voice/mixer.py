"""PipeWire virtual microphone for meet mode.

Provisions two adapter nodes:

* ``VirtualSpeaker`` (Audio/Sink) — receives the agent's TTS audio
* ``VirtualMic`` (Audio/Source/Virtual) — appears as a microphone in
  Meet/Zoom/Teams

Then links ``VirtualSpeaker:monitor_* -> VirtualMic:input_*`` and the real
microphone's capture ports -> VirtualMic inputs, so the app receives a mix
of the Architect's voice and the agent's voice.
"""

from __future__ import annotations

import re
import subprocess
import time

from .capture import default_source_name

VIRTUAL_SINK = "VirtualSpeaker"
VIRTUAL_MIC = "VirtualMic"


def _run(cmd: list[str]) -> str:
    out = subprocess.run(cmd, capture_output=True, timeout=10)
    return out.stdout.decode() + out.stderr.decode()


def _find_serial(name: str) -> str | None:
    """Object serial for a node.name from the pw-cli registry listing."""
    out = _run(["pw-cli", "list-objects"])
    cur_id: str | None = None
    for line in out.splitlines():
        m = re.match(r"\s*id\s+(\d+),", line)
        if m:
            cur_id = m.group(1)
        if f'node.name = "{name}"' in line and cur_id is not None:
            return cur_id
    return None


def _create_node(name: str, media_class: str) -> str | None:
    props = ("{ factory.name=support.null-audio-sink "
             f"node.name={name} media.class={media_class} "
             "object.linger=true audio.channels=2 "
             "audio.position=[ FL FR ] }")
    _run(["pw-cli", "create-node", "adapter", props])
    # pw-cli 1.x does not echo the created object's serial; poll the
    # registry until WirePlumber publishes the node.
    deadline = time.time() + 3.0
    while time.time() < deadline:
        serial = _find_serial(name)
        if serial is not None:
            return serial
        time.sleep(0.15)
    return None


def _link(src: str, dst: str) -> bool:
    out = _run(["pw-link", src, dst])
    return out.strip() == "" or "linked" in out.lower()


def _ports(node_name: str, direction: str, kind: str) -> list[str]:
    """Ports of a node. direction: ``-o`` outputs or ``-i`` inputs."""
    out = _run(["pw-link", direction])
    ports = []
    for line in out.splitlines():
        line = line.strip().rstrip(":")
        if line.startswith(node_name + ":") and kind in line:
            ports.append(line)
    return ports


def _capture_ports(source_name: str) -> list[str]:
    return _ports(source_name, "-o", "capture_")


def _playback_ports(sink_name: str) -> list[str]:
    return _ports(sink_name, "-i", "playback_")


def _default_sink_name() -> str | None:
    out = _run(["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"])
    m = re.search(r'node\.name\s*=\s*"([^"]+)"', out)
    return m.group(1) if m else None


class VirtualMic:
    """Provisioning/teardown lifecycle for the virtual microphone."""

    def __init__(self):
        self.serials: dict[str, str] = {}
        self.linked: list[tuple[str, str]] = []
        self.active = False

    def provision(self, mix_real_mic: bool = True) -> dict:
        """Create nodes + links. Returns port map."""
        if self.active:
            return {"active": True, "note": "already provisioned"}
        # Nodes are created with object.linger=true and survive process
        # death: destroy stale instances before creating fresh ones.
        cleaned = []
        for stale in (VIRTUAL_SINK, VIRTUAL_MIC):
            serial = _find_serial(stale)
            if serial is not None:
                _run(["pw-cli", "destroy", serial])
                cleaned.append(stale)
        s_serial = _create_node(VIRTUAL_SINK, "Audio/Sink")
        m_serial = _create_node(VIRTUAL_MIC, "Audio/Source/Virtual")
        if not m_serial:
            return {"active": False,
                    "error": "could not create VirtualMic via pw-cli"}
        self.serials = {"sink": s_serial or "", "mic": m_serial}
        time.sleep(0.6)  # let WirePlumber publish ports

        # Topology (a dst port accepts ONE link, so VirtualSpeaker is the
        # mix point, not VirtualMic's inputs):
        #   real-mic:capture_*  ─┐
        #                        ├─→ VirtualSpeaker:playback_*  (mix)
        #   TTS playback        ─┘        │
        #                      VirtualSpeaker:monitor_* ─→ VirtualMic:input_*
        # Local echo is NOT linked here (it would echo the Architect's own
        # mic back); the TTS player targets VirtualSpeaker AND the default
        # sink with two concurrent pw-play streams instead.
        links = []
        for ch in ("FL", "FR"):
            src = f"{VIRTUAL_SINK}:monitor_{ch}"
            dst = f"{VIRTUAL_MIC}:input_{ch}"
            if _link(src, dst):
                links.append((src, dst))
        if mix_real_mic:
            real = default_source_name()
            if real:
                caps = _capture_ports(real)[:2]
                plays = _playback_ports(VIRTUAL_SINK)[:2]
                for cap, play in zip(caps, plays, strict=False):
                    if _link(cap, play):
                        links.append((cap, play))
        self.linked = links
        self.active = bool(links)
        return {"active": self.active, "links": len(links),
                "cleaned_stale": cleaned,
                "virtual_source": VIRTUAL_MIC,
                "playback_target": VIRTUAL_SINK,
                "instruction": "Seleccione 'VirtualMic' como micrófono en la app de llamadas"}

    def teardown(self) -> dict:
        for src, dst in self.linked:
            _run(["pw-link", "-d", src, dst])
        self.linked = []
        destroyed = []
        for kind, serial in self.serials.items():
            if serial:
                _run(["pw-cli", "destroy", serial])
                destroyed.append(kind)
        self.serials = {}
        self.active = False
        return {"destroyed": destroyed}

    def status(self) -> dict:
        out = _run(["pw-cli", "list-objects"])
        return {"active": self.active,
                VIRTUAL_SINK: VIRTUAL_SINK in out,
                VIRTUAL_MIC: VIRTUAL_MIC in out,
                "links": len(self.linked)}
