"""Tests for the arqux-comms extension (BLP-017)."""

from __future__ import annotations

from arqux.comms import config as cfg
from arqux.comms.bridge import Bridge
from arqux.comms.inbox import Inbox
from arqux.comms.telegram import TelegramChannel


def test_inbox_dedup_and_listen() -> None:
    box = Inbox()
    assert box.put({"id": 1, "text": "hola"}) is True
    assert box.put({"id": 1, "text": "hola"}) is False  # duplicate id
    assert len(box.unread()) == 1
    assert box.listen(0.5)["text"] == "hola"
    assert box.listen(0.5) is None


def test_allowlist_parsing(monkeypatch) -> None:
    monkeypatch.setenv(cfg.ALLOWLIST_ENV, "111, 222 ;333")
    assert cfg.allowlist() == {"111", "222", "333"}


def test_egress_default_off(monkeypatch) -> None:
    monkeypatch.delenv(cfg.EGRESS_ENV, raising=False)
    assert cfg.egress_enabled() is False
    monkeypatch.setenv(cfg.EGRESS_ENV, "on")
    assert cfg.egress_enabled() is True


def test_send_failclosed(monkeypatch) -> None:
    # egress OFF → refuse (no network)
    monkeypatch.setenv(cfg.EGRESS_ENV, "off")
    ch = TelegramChannel("dummy", Inbox(), allowlist={"1"})
    assert ch.send("1", "x")["error"] == "egress_disabled"
    # egress ON but destination not in allowlist → refuse (no network)
    monkeypatch.setenv(cfg.EGRESS_ENV, "on")
    assert ch.send("999", "x")["error"] == "destination_not_allowed"
    # empty allowlist is fail-closed
    ch2 = TelegramChannel("dummy", Inbox(), allowlist=set())
    assert ch2.send("1", "x")["error"] == "destination_not_allowed"


def test_redact(monkeypatch) -> None:
    monkeypatch.setenv(cfg.TELEGRAM_TOKEN_ENV, "SECRET123")
    assert "SECRET123" not in cfg.redact("token=SECRET123 end")


def test_bridge_record(monkeypatch, tmp_path) -> None:
    import arqux.comms.bridge as bridge_mod
    monkeypatch.setattr(bridge_mod, "state_dir", lambda: tmp_path)
    b = Bridge(enabled=True)
    assert b.record({"id": 1, "text": "hola"})["logged"] is True
    assert (tmp_path / "inbox_log.ndjson").exists()
