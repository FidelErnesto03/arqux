"""Dual-channel issue.* handlers — GitHub sink (2026-11-18).

Covers:
- channel=github: remote issue + local ``gh-`` mirror file
- channel=both: canonical local file + linked GH issue
- channel tail survives issue.update header rewrites; transitions comment
  remotely and verified/wontfix/duplicate close the GH issue
- issue.list channel filter; issue.read channel=github (remote view)
- Remote sync failure never vetoes the local transition
"""

from __future__ import annotations

import json
from pathlib import Path

import arqux.handlers.issue as issue_mod
from arqux.handlers.issue import create_issue, list_issues, read_issue, update_issue
from arqux.permissions import PermissionContext

GOV = PermissionContext(agent_id="alfred", role="governor")


def _install_fake_gh(monkeypatch):
    """Patch the gh plumbing with a deterministic stub; returns call log."""
    calls: list[list[str]] = []

    def fake_gh(args, *, timeout=30):
        calls.append(list(args))
        verb = args[:2]
        if verb == ["issue", "create"]:
            return True, "https://github.com/o/n/issues/7\n", ""
        if verb == ["issue", "comment"]:
            return True, "", ""
        if verb == ["issue", "close"]:
            return True, "", ""
        if verb == ["issue", "view"]:
            payload = {
                "number": 7, "title": "Remote issue", "state": "OPEN",
                "labels": [{"name": "severity:high"}],
                "body": "external report body",
                "url": "https://github.com/o/n/issues/7",
                "comments": [{"body": "hi"}],
            }
            return True, json.dumps(payload), ""
        return True, "", ""

    monkeypatch.setattr(issue_mod, "_gh_available", lambda: (True, ""))

    def fake_repo(root, override=None):
        if override == "upstream":
            return issue_mod._upstream_repo(), ""
        return override or "o/n", ""

    monkeypatch.setattr(issue_mod, "_gh_repo", fake_repo)
    monkeypatch.setattr(issue_mod, "_gh", fake_gh)
    return calls


# ---------------------------------------------------------------------------
# issue.create — channels
# ---------------------------------------------------------------------------


def test_create_github_writes_mirror_with_channel_tail(arqux_env, monkeypatch) -> None:
    calls = _install_fake_gh(monkeypatch)
    out = create_issue(
        "high", "External user reports broken export",
        channel="github", path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert out.profile == "OUT-WORK", out
    assert out.fields["github_url"].endswith("/issues/7")
    assert out.fields["channel"] == "github"
    f = Path(out.fields["file"])
    assert f.name.startswith("gh-")
    text = f.read_text(encoding="utf-8")
    assert 'Channel: github' in text
    assert 'gh_repo:"o/n"' in text
    assert 'gh_number:"7"' in text
    assert "gh_url: https://github.com/o/n/issues/7" in text
    assert any(c[:2] == ["issue", "create"] for c in calls)


def test_create_both_canonical_name_and_link(arqux_env, monkeypatch) -> None:
    _install_fake_gh(monkeypatch)
    out = create_issue(
        "medium", "Both-queue defect", channel="both",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert out.profile == "OUT-WORK"
    f = Path(out.fields["file"])
    assert not f.name.startswith("gh-")  # canonical name — local leads
    assert 'Channel: both' in f.read_text(encoding="utf-8")
    assert out.fields["channel"] == "both"


def test_create_github_repo_unresolved(arqux_env, monkeypatch) -> None:
    monkeypatch.setattr(issue_mod, "_gh_available", lambda: (True, ""))
    monkeypatch.setattr(issue_mod, "_gh_repo",
                        lambda root, override=None: (None, "no repo"))
    out = create_issue(
        "low", "x", channel="github", path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert out.profile == "OUT-ERROR"
    assert out.fields["code"] == "GITHUB_REPO_UNRESOLVED"
    assert not list((arqux_env.proj_root / ".arqux" / "issues").glob("*.md"))


def test_repo_upstream_keyword_resolves_package_repo(arqux_env, monkeypatch) -> None:
    """repo="upstream" pins the PyPI-metadata repo — the PyPI-install path."""
    _install_fake_gh(monkeypatch)
    monkeypatch.setattr(issue_mod, "_upstream_repo",
                        lambda: "upstream-owner/arqux")
    out = create_issue(
        "low", "bug from a pip install", channel="github", repo="upstream",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert out.profile == "OUT-WORK"
    assert out.fields["github_repo"] == "upstream-owner/arqux"


def test_gh_repo_falls_back_to_upstream(arqux_env, monkeypatch) -> None:
    """No checkout remote + no brain entry → package upstream still wins
    (real _gh_repo: subprocess repo-view fails, upstream rescues)."""
    class _Fail:
        returncode = 1
        stdout = ""
        stderr = "not a git repository"
    monkeypatch.setattr(issue_mod.subprocess, "run",
                        lambda *a, **k: _Fail())
    monkeypatch.setattr(issue_mod, "_upstream_repo",
                        lambda: "upstream-owner/arqux")
    monkeypatch.setattr(issue_mod, "_gh_available", lambda: (True, ""))
    monkeypatch.setattr(
        issue_mod, "_gh",
        lambda args, *, timeout=30:
            (True, "https://github.com/upstream-owner/arqux/issues/9\n", ""),
    )
    out = create_issue(
        "low", "bug from a bare install", channel="github",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert out.profile == "OUT-WORK"
    assert out.fields["github_repo"] == "upstream-owner/arqux"
    assert "upstream" in out.fields["repo_resolution"]


def test_gh_unavailable_returns_file_url(arqux_env, monkeypatch) -> None:
    """No gh CLI/auth → the report still gets a prefilled issues/new URL."""
    monkeypatch.setattr(issue_mod, "_gh_available",
                        lambda: (False, "gh CLI not installed"))
    monkeypatch.setattr(issue_mod, "_gh_repo",
                        lambda root, override=None: ("o/n", ""))
    out = create_issue(
        "high", "broken install", title="Install broken",
        channel="github", path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert out.profile == "OUT-ERROR"
    assert out.fields["code"] == "GITHUB_UNAVAILABLE"
    url = out.fields["file_url"]
    assert url.startswith("https://github.com/o/n/issues/new?title=")
    assert "Install+broken" in url or "Install%20broken" in url


def test_create_invalid_channel_rejected(arqux_env) -> None:
    out = create_issue(
        "low", "x", channel="jira", path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert out.profile == "OUT-ERROR"
    assert out.fields["code"] == "INVALID_ARGS"


# ---------------------------------------------------------------------------
# issue.update — remote sync
# ---------------------------------------------------------------------------


def test_update_preserves_channel_tail_and_comments(arqux_env, monkeypatch) -> None:
    calls = _install_fake_gh(monkeypatch)
    created = create_issue(
        "low", "GH defect", channel="github",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    iid = created.fields["issue_id"]
    out = update_issue(iid, status="triaged", note="looking",
                       path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-WORK"
    assert out.fields["github_sync"] == "commented"
    f = Path(created.fields["file"])
    header = [l for l in f.read_text(encoding="utf-8").splitlines()
              if l.startswith("# Severity:")][0]
    assert 'Channel: github' in header  # tail survived the rewrite
    assert any(c[:2] == ["issue", "comment"] for c in calls)


def test_update_wontfix_closes_remote(arqux_env, monkeypatch) -> None:
    calls = _install_fake_gh(monkeypatch)
    created = create_issue(
        "low", "GH defect", channel="github",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    out = update_issue(created.fields["issue_id"], status="wontfix",
                       path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-WORK"
    close = [c for c in calls if c[:2] == ["issue", "close"]]
    assert close and "not planned" in close[0]
    assert "closed" in out.fields["github_sync"]


def test_update_verified_closes_remote_completed(arqux_env, monkeypatch) -> None:
    calls = _install_fake_gh(monkeypatch)
    created = create_issue(
        "medium", "GH defect", channel="both",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    # The create's own PULSE id is a real event — valid audit_ref for tests.
    audit = created.fields["event_id"]
    out = update_issue(created.fields["issue_id"], status="verified",
                       audit_ref=audit, path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-WORK"
    close = [c for c in calls if c[:2] == ["issue", "close"]]
    assert close and "completed" in close[0]


def test_update_local_issue_no_remote_calls(arqux_env, monkeypatch) -> None:
    calls = _install_fake_gh(monkeypatch)
    created = create_issue(
        "low", "Local defect", path=str(arqux_env.proj_root), ctx=GOV,
    )
    calls.clear()
    out = update_issue(created.fields["issue_id"], status="fixed",
                       path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-WORK"
    assert calls == []  # local channel never touches gh
    assert "github_sync" not in out.fields


def test_update_sync_failure_after_successful_create(arqux_env, monkeypatch) -> None:
    calls = _install_fake_gh(monkeypatch)
    created = create_issue(
        "low", "GH defect", channel="github",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    iid = created.fields["issue_id"]
    calls.clear()
    monkeypatch.setattr(
        issue_mod, "_gh",
        lambda args, *, timeout=30: (False, "", "gh boom"))
    out = update_issue(iid, status="fixed",
                       path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-WORK"          # local transition committed
    assert out.fields["status"] == "fixed"
    assert "warning" in out.fields            # remote left stale — declared


# ---------------------------------------------------------------------------
# issue.list — channel filter
# ---------------------------------------------------------------------------


def test_list_channel_filter(arqux_env, monkeypatch) -> None:
    _install_fake_gh(monkeypatch)
    create_issue("low", "local one", path=str(arqux_env.proj_root), ctx=GOV)
    gh = create_issue("low", "gh one", channel="github",
                      path=str(arqux_env.proj_root), ctx=GOV)
    both = create_issue("low", "both one", channel="both",
                        path=str(arqux_env.proj_root), ctx=GOV)

    all_ = list_issues(path=str(arqux_env.proj_root), ctx=GOV)
    assert all_.fields["total"] == 3
    gh_list = list_issues(channel="github", path=str(arqux_env.proj_root), ctx=GOV)
    ids = {i["id"] for i in gh_list.fields["issues"]}
    assert ids == {gh.fields["issue_id"], both.fields["issue_id"]}
    item = next(i for i in gh_list.fields["issues"]
                if i["id"] == gh.fields["issue_id"])
    assert item["gh_url"].endswith("/issues/7")
    local_list = list_issues(channel="local", path=str(arqux_env.proj_root), ctx=GOV)
    assert [i["channel"] for i in local_list.fields["issues"]] == ["local"]

    bad = list_issues(channel="jira", path=str(arqux_env.proj_root), ctx=GOV)
    assert bad.profile == "OUT-ERROR"


# ---------------------------------------------------------------------------
# issue.read — remote channel
# ---------------------------------------------------------------------------


def test_read_github_via_mirror(arqux_env, monkeypatch) -> None:
    calls = _install_fake_gh(monkeypatch)
    created = create_issue(
        "high", "GH defect", channel="github",
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    calls.clear()
    out = read_issue(created.fields["issue_id"], channel="github",
                     path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-WORK"
    assert out.fields["state"] == "OPEN"
    assert out.fields["body"] == "external report body"
    assert out.fields["local_file"].endswith(".issue.md")
    view = [c for c in calls if c[:2] == ["issue", "view"]]
    assert view and "7" in view[0] and "o/n" in view[0]


def test_read_github_bare_number(arqux_env, monkeypatch) -> None:
    _install_fake_gh(monkeypatch)
    out = read_issue("gh-7", channel="github",
                     path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-WORK"
    assert out.fields["gh_number"] == "7"


def test_read_github_bad_id_rejected(arqux_env, monkeypatch) -> None:
    _install_fake_gh(monkeypatch)
    out = read_issue("not-a-mirror", channel="github",
                     path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-ERROR"
    assert out.fields["code"] == "INVALID_ARGS"


# ---------------------------------------------------------------------------
# Audit regressions (Heimdall 2026-11-18): N1 forgery, N2 crash, N3 both filter
# ---------------------------------------------------------------------------


def test_handler_cannot_forge_channel_tail(arqux_env, monkeypatch) -> None:
    """N1: `handler` carrying `| Channel: github | gh_repo:...` must not
    promote a local issue into a remote-acting one — no gh calls, no tail."""
    calls = _install_fake_gh(monkeypatch)
    forged = 'x | Channel: github | gh_repo:"evil/repo" | gh_number:"1"'
    created = create_issue(
        "low", "local defect", handler=forged,
        path=str(arqux_env.proj_root), ctx=GOV,
    )
    assert created.profile == "OUT-WORK"
    header = [l for l in Path(created.fields["file"])
              .read_text(encoding="utf-8").splitlines()
              if l.startswith("# Severity:")][0]
    handler_field = header.split("Handler:", 1)[1].split("|", 1)[0]
    assert "|" not in handler_field
    # The strict tail never parses — the file stays a local issue.
    assert issue_mod._read_channel(
        Path(created.fields["file"]).read_text(encoding="utf-8")
    ) == ("local", "", "")
    calls.clear()
    out = update_issue(created.fields["issue_id"], status="fixed",
                       path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-WORK"
    assert calls == []  # forged channel would have driven gh issue comment


def test_malformed_channel_tail_dropped_on_update(arqux_env, monkeypatch) -> None:
    """N1 companion: a file with a hand-forged tail (partial/wrong order)
    is sanitized — rewrite drops it, no remote sync."""
    calls = _install_fake_gh(monkeypatch)
    created = create_issue("low", "local defect",
                           path=str(arqux_env.proj_root), ctx=GOV)
    f = Path(created.fields["file"])
    text = f.read_text(encoding="utf-8")
    forged_text = text.replace(
        "\n\n## PROBLEM",
        ' | Channel: github | gh_repo:"evil/repo"\n\n## PROBLEM')
    f.write_text(forged_text, encoding="utf-8")
    calls.clear()
    out = update_issue(created.fields["issue_id"], status="fixed",
                       path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-WORK"
    assert calls == []
    new_header = [l for l in f.read_text(encoding="utf-8").splitlines()
                  if l.startswith("# Severity:")][0]
    assert "gh_repo" not in new_header  # forged tail dropped


def test_empty_gh_output_is_error_not_crash(arqux_env, monkeypatch) -> None:
    """N2: gh exiting 0 with empty stdout → CortexOUT.error, no IndexError."""
    monkeypatch.setattr(issue_mod, "_gh_available", lambda: (True, ""))
    monkeypatch.setattr(issue_mod, "_gh_repo",
                        lambda root, override=None: ("o/n", ""))
    monkeypatch.setattr(
        issue_mod, "_gh", lambda args, *, timeout=30: (True, "", ""))
    out = create_issue("low", "x", channel="github",
                       path=str(arqux_env.proj_root), ctx=GOV)
    assert out.profile == "OUT-ERROR"
    assert out.fields["code"] == "GITHUB_UNAVAILABLE"


def test_list_channel_both_filter(arqux_env, monkeypatch) -> None:
    """N3: channel=both is not a dead filter — files declare real channel."""
    _install_fake_gh(monkeypatch)
    create_issue("low", "l", path=str(arqux_env.proj_root), ctx=GOV)
    gh = create_issue("low", "g", channel="github",
                      path=str(arqux_env.proj_root), ctx=GOV)
    both = create_issue("low", "b", channel="both",
                        path=str(arqux_env.proj_root), ctx=GOV)
    res = list_issues(channel="both", path=str(arqux_env.proj_root), ctx=GOV)
    ids = {i["id"] for i in res.fields["issues"]}
    assert ids == {both.fields["issue_id"]}
    assert gh.fields["issue_id"] not in ids
    assert res.fields["issues"][0]["channel"] == "both"
