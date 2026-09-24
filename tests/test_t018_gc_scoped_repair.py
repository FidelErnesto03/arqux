"""Regression tests for T-018 — cortex.gc scoped repair.

Covers:
- section/sigil/name filters restrict which duplicate groups are
  affected; unfiltered calls keep the original whole-file behaviour
- keep='last' conserves the LAST occurrences in file order (metrics:
  retains the most recent values)
- mode='rename' preserves every occurrence and assigns extras the next
  sequential numeric id in the (section, sigil) namespace (global max
  + 1, incremented per rename, chronological order); pulse ``event``
  attrs are updated consistently; names without a numeric suffix get
  ``_001``, ``_002``... appended
- invalid keep/mode -> INVALID_ARGS
- dry_run previews both modes accurately (incl. assigned new names)
"""

from __future__ import annotations

from pathlib import Path

from arqux.core.state import crud_read
from arqux.handlers.cortex import gc_handler
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")

# $6 dup groups: AUD:E_0157 x3, AUD:E_0158 x2, KNW:tasks_done x3,
# KNW:tasks_active x2.  AUD:E_0160 is NOT a dupe — it sets the global
# AUD numeric max to 160, so renames must start at E_0161.
# $7 dup group: LNG:________codec_cortex x2.
_BRAIN = """$0

# AUD   | audit      | attrs      | M | Prefrontal     | Verification/audit record
# KNW   | knowledge  | attrs      | B | Semantic       | knowledge
# LNG   | lesson     | attrs      | M | Episodic       | lesson

$6: PULSE

AUD:E_0157{date:"2026-07-20", event:"E-0157", task:"-", kind:"handler_call", agent:"a", result:"r1", evidence:"r1"}
AUD:E_0157{date:"2026-08-17", event:"E-0157", task:"-", kind:"handler_call", agent:"a", result:"r2", evidence:"r2"}
AUD:E_0157{date:"2026-08-18", event:"E-0157", task:"-", kind:"handler_call", agent:"a", result:"r3", evidence:"r3"}
AUD:E_0158{date:"2026-08-19", event:"E-0158", task:"-", kind:"note", agent:"a", result:"r4", evidence:"r4"}
AUD:E_0158{date:"2026-08-20", event:"E-0158", task:"-", kind:"note", agent:"a", result:"r5", evidence:"r5"}
AUD:E_0160{date:"2026-08-21", event:"E-0160", task:"-", kind:"note", agent:"a", result:"r6", evidence:"r6"}
KNW:tasks_done{name:"tasks_done", value:"1", updated:"a"}
KNW:tasks_done{name:"tasks_done", value:"2", updated:"b"}
KNW:tasks_done{name:"tasks_done", value:"3", updated:"c"}
KNW:tasks_active{name:"tasks_active", value:"9", updated:"a"}
KNW:tasks_active{name:"tasks_active", value:"7", updated:"b"}

$7: LESSONS

LNG:________codec_cortex{lesson:"l1", prevention:"p"}
LNG:________codec_cortex{lesson:"l2", prevention:"p"}
"""

# C1 regression fixture: a section mixing AUD:E_NNNN dupes with a
# DIFFERENT sigil holding a higher numeric-suffixed name (KNW:m_2026)
# and a same-name entry under another sigil (KNW:E_0161).  The rename
# counter and used-name set must be scoped to (section, sigil) — AUD
# extras continue from the AUD max (160), not the section max (2026),
# and KNW:E_0161 must not block AUD:E_0161.
_MIXED_BRAIN = """$0

# AUD   | audit      | attrs      | M | Prefrontal     | Verification/audit record
# KNW   | knowledge  | attrs      | B | Semantic       | knowledge

$6: PULSE

AUD:E_0157{date:"t1", event:"E-0157", task:"-", kind:"note", agent:"a", result:"r1", evidence:"r1"}
AUD:E_0157{date:"t2", event:"E-0157", task:"-", kind:"note", agent:"a", result:"r2", evidence:"r2"}
AUD:E_0157{date:"t3", event:"E-0157", task:"-", kind:"note", agent:"a", result:"r3", evidence:"r3"}
AUD:E_0160{date:"t4", event:"E-0160", task:"-", kind:"note", agent:"a", result:"r4", evidence:"r4"}
KNW:m_2026{name:"m_2026", value:"x"}
KNW:E_0161{name:"E_0161", value:"x"}
"""


def _brain(tmp_path: Path) -> Path:
    f = tmp_path / "brain.cortex"
    f.write_text(_BRAIN)
    return f


def _names(f: Path, selector: str) -> list[str]:
    return [e["name"] for e in crud_read(f, selector)["entries"]]


def _events(f: Path) -> list[str]:
    return [
        e["value"].get("event")
        for e in crud_read(f, "$6/AUD:*")["entries"]
    ]


def _values(f: Path, knw_name: str) -> list[str]:
    return [
        e["value"].get("value")
        for e in crud_read(f, f"$6/KNW:{knw_name}")["entries"]
    ]


def _names_prefixed(f: Path, selector: str, prefix: str) -> list[str]:
    return [
        e["name"]
        for e in crud_read(f, selector)["entries"]
        if e["name"] == prefix or e["name"].startswith(f"{prefix}_")
    ]


# ---------------------------------------------------------------------------
# scoped dedupe: filters
# ---------------------------------------------------------------------------


def test_gc_section_filter_only_affects_that_section(tmp_path: Path) -> None:
    """section='$6' dedupes $6 groups; $7 LNG dupes stay untouched."""
    f = _brain(tmp_path)
    out = gc_handler(str(f), section="$6", dry_run=False, force=True)
    assert out.profile == "OUT-WORK", str(out.fields)
    # $6: E_0157(-2), E_0158(-1), tasks_done(-2), tasks_active(-1) = 6
    assert out.fields["removed"] == 6
    assert out.fields["matched_groups"] == 4
    assert out.fields["skipped_groups"] == 1
    # $7 untouched
    assert _names(f, "$7/LNG:*") == [
        "________codec_cortex", "________codec_cortex",
    ]


def test_gc_section_filter_accepts_bare_number(tmp_path: Path) -> None:
    """section='6' (no $ prefix) is equivalent to '$6'."""
    f = _brain(tmp_path)
    out = gc_handler(str(f), section="6", dry_run=False, force=True)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["removed"] == 6


def test_gc_sigil_filter_only_affects_that_sigil(tmp_path: Path) -> None:
    """sigil='KNW' dedupes only KNW groups; AUD dupes stay."""
    f = _brain(tmp_path)
    out = gc_handler(str(f), sigil="KNW", dry_run=False, force=True)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["removed"] == 3  # tasks_done(-2) + tasks_active(-1)
    aud = _names(f, "$6/AUD:*")
    assert aud.count("E_0157") == 3
    assert aud.count("E_0158") == 2


def test_gc_name_filter_only_affects_that_name(tmp_path: Path) -> None:
    """name='E_0157' dedupes only that group; E_0158 dupes stay."""
    f = _brain(tmp_path)
    out = gc_handler(
        str(f), section="$6", sigil="AUD", name="E_0157",
        dry_run=False, force=True,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["removed"] == 2
    assert out.fields["matched_groups"] == 1
    assert out.fields["skipped_groups"] == 4
    aud = _names(f, "$6/AUD:*")
    assert aud.count("E_0157") == 1
    assert aud.count("E_0158") == 2


def test_gc_filter_matching_nothing_reports_skipped(tmp_path: Path) -> None:
    """A filter matching no group removes nothing and reports skips."""
    f = _brain(tmp_path)
    out = gc_handler(str(f), name="no_such_name", dry_run=False, force=True)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["removed"] == 0
    assert out.fields["matched_groups"] == 0
    assert out.fields["skipped_groups"] == 5
    assert "skipped" in out.message
    # File content untouched — all dupes still there.
    assert _names(f, "$7/LNG:*") == [
        "________codec_cortex", "________codec_cortex",
    ]


def test_gc_unfiltered_keeps_whole_file_behaviour(tmp_path: Path) -> None:
    """No filters = every duplicate group is deduped (current behaviour)."""
    f = _brain(tmp_path)
    out = gc_handler(str(f), dry_run=False, force=True)
    assert out.profile == "OUT-WORK", str(out.fields)
    # 2 + 1 + 2 + 1 + 1 = 7 removed across 5 groups
    assert out.fields["removed"] == 7
    assert out.fields["matched_groups"] == 5
    assert out.fields["skipped_groups"] == 0


# ---------------------------------------------------------------------------
# keep='last'
# ---------------------------------------------------------------------------


def test_gc_keep_last_retains_latest_occurrence(tmp_path: Path) -> None:
    """keep='last' keeps the most recent metric value, not the first."""
    f = _brain(tmp_path)
    out = gc_handler(
        str(f), sigil="KNW", name="tasks_done", keep="last",
        dry_run=False, force=True,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["removed"] == 2
    assert _values(f, "tasks_done") == ["3"]


def test_gc_keep_last_honours_first_kept(tmp_path: Path) -> None:
    """keep='last' + first_kept=2 conserves the two latest occurrences."""
    f = _brain(tmp_path)
    out = gc_handler(
        str(f), sigil="KNW", name="tasks_done", keep="last", first_kept=2,
        dry_run=False, force=True,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["removed"] == 1
    assert _values(f, "tasks_done") == ["2", "3"]


def test_gc_keep_last_report_kept_names(tmp_path: Path) -> None:
    f = _brain(tmp_path)
    out = gc_handler(str(f), sigil="KNW", keep="last", first_kept=2, dry_run=True)
    dup = next(d for d in out.fields["duplicates"] if d["name"] == "tasks_done")
    assert dup["keep"] == "last"
    assert len(dup["kept_names"]) == 2


# ---------------------------------------------------------------------------
# mode='rename'
# ---------------------------------------------------------------------------


def test_gc_rename_preserves_all_and_assigns_sequential_names(
    tmp_path: Path,
) -> None:
    """rename keeps every occurrence; extras get global-max+1 ids in
    chronological file order; embedded event attrs follow."""
    f = _brain(tmp_path)
    out = gc_handler(
        str(f), section="$6", sigil="AUD", mode="rename",
        dry_run=False, force=True,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["renamed"] == 3
    assert out.fields["removed"] == 0
    assert out.fields["matched_groups"] == 2

    # All 6 AUD entries preserved, names unique, file order kept.
    aud = _names(f, "$6/AUD:*")
    assert len(aud) == 6
    assert len(set(aud)) == 6
    # Global AUD max was 160 -> extras continue at 161, in file order:
    # E_0157 kept on first occurrence; its 2 extras -> E_0161, E_0162;
    # E_0158 kept on first occurrence; its extra -> E_0163.
    assert aud == ["E_0157", "E_0161", "E_0162", "E_0158", "E_0163", "E_0160"]
    # event attrs stay consistent with the new names (hyphen form).
    assert _events(f) == [
        "E-0157", "E-0161", "E-0162", "E-0158", "E-0163", "E-0160",
    ]


def test_gc_rename_report_lists_new_names(tmp_path: Path) -> None:
    f = _brain(tmp_path)
    out = gc_handler(
        str(f), section="$6", sigil="AUD", mode="rename",
        dry_run=False, force=True,
    )
    items = out.fields["duplicates"]
    assert [i["action"] for i in items] == ["renamed"] * 3
    assert [i["new_name"] for i in items] == ["E_0161", "E_0162", "E_0163"]
    assert all(i["event_updated"] for i in items)
    assert [i["name"] for i in items] == ["E_0157", "E_0157", "E_0158"]


def test_gc_rename_scoped_to_single_group(tmp_path: Path) -> None:
    """name='E_0157' renames only that group; E_0158 stays duplicated."""
    f = _brain(tmp_path)
    out = gc_handler(
        str(f), section="$6", sigil="AUD", name="E_0157", mode="rename",
        dry_run=False, force=True,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["renamed"] == 2
    aud = _names(f, "$6/AUD:*")
    assert aud == ["E_0157", "E_0161", "E_0162", "E_0158", "E_0158", "E_0160"]


def test_gc_rename_non_numeric_suffix_appends_001(tmp_path: Path) -> None:
    """Names without a trailing numeric suffix get _001, _002, ..."""
    f = _brain(tmp_path)
    out = gc_handler(
        str(f), sigil="KNW", mode="rename", dry_run=False, force=True,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["renamed"] == 3
    assert _names_prefixed(f, "$6/KNW:*", "tasks_done") == [
        "tasks_done", "tasks_done_001", "tasks_done_002",
    ]
    assert _names_prefixed(f, "$6/KNW:*", "tasks_active") == [
        "tasks_active", "tasks_active_001",
    ]


def test_gc_rename_keep_last_renames_earliest(tmp_path: Path) -> None:
    """keep='last' + rename: the LATEST occurrence keeps the name; the
    earlier ones are renamed in file order."""
    f = _brain(tmp_path)
    out = gc_handler(
        str(f), sigil="AUD", name="E_0157", mode="rename", keep="last",
        dry_run=False, force=True,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["renamed"] == 2
    aud = _names(f, "$6/AUD:*")
    # Earliest two E_0157 occurrences renamed (file order); last keeps id.
    assert aud == ["E_0161", "E_0162", "E_0157", "E_0158", "E_0158", "E_0160"]


def test_gc_rename_requires_force(tmp_path: Path) -> None:
    f = _brain(tmp_path)
    out = gc_handler(str(f), mode="rename", dry_run=False, force=False)
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("code") == "CONFIRM_REQUIRED"
    assert "rename" in out.message
    # Nothing changed.
    assert _names(f, "$6/AUD:*").count("E_0157") == 3


def test_gc_rename_counter_scoped_to_same_sigil(tmp_path: Path) -> None:
    """C1 regression: rename counter + used-set are per (section, sigil).

    A different sigil's high numeric-suffixed name (KNW:m_2026) must NOT
    seed the AUD counter — extras continue from the AUD max (160), not
    the section max (2026).  A same-named entry under another sigil
    (KNW:E_0161) must NOT block the AUD rename to E_0161 either.
    """
    f = tmp_path / "brain.cortex"
    f.write_text(_MIXED_BRAIN)
    out = gc_handler(
        str(f), sigil="AUD", mode="rename", dry_run=False, force=True,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["renamed"] == 2
    aud = _names(f, "$6/AUD:*")
    assert aud == ["E_0157", "E_0161", "E_0162", "E_0160"]
    assert _events(f) == ["E-0157", "E-0161", "E-0162", "E-0160"]
    # Other-sigil entries untouched (same literal name is fine).
    assert _names(f, "$6/KNW:*") == ["m_2026", "E_0161"]


def test_gc_rename_single_atomic_rewrite(
    tmp_path: Path, monkeypatch,
) -> None:
    """rename mode also performs ONE file rewrite for the whole run."""
    import arqux.handlers.cortex.gc as gc_mod

    f = _brain(tmp_path)
    writes = {"n": 0}
    real = gc_mod.atomic_write_json

    def counting(doc, path, **kwargs):
        writes["n"] += 1
        return real(doc, path, **kwargs)

    monkeypatch.setattr(gc_mod, "atomic_write_json", counting)
    out = gc_handler(
        str(f), sigil="AUD", mode="rename", dry_run=False, force=True,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert writes["n"] == 1


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def test_gc_invalid_keep_returns_invalid_args(tmp_path: Path) -> None:
    f = _brain(tmp_path)
    out = gc_handler(str(f), keep="middle", dry_run=False, force=True)
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("code") == "INVALID_ARGS"
    assert "keep" in out.message
    assert _names(f, "$6/AUD:*").count("E_0157") == 3


def test_gc_invalid_mode_returns_invalid_args(tmp_path: Path) -> None:
    f = _brain(tmp_path)
    out = gc_handler(str(f), mode="obliterate", dry_run=False, force=True)
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("code") == "INVALID_ARGS"
    assert "mode" in out.message
    assert _names(f, "$6/AUD:*").count("E_0157") == 3


# ---------------------------------------------------------------------------
# dry_run previews
# ---------------------------------------------------------------------------


def test_gc_dedupe_dry_run_previews_scoped_removals(tmp_path: Path) -> None:
    f = _brain(tmp_path)
    out = gc_handler(str(f), section="$6", sigil="KNW", dry_run=True)
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["removed"] == 0
    assert out.fields["would_remove"] == 3
    assert out.fields["would_rename"] == 0
    assert out.fields["matched_groups"] == 2
    assert {d["action"] for d in out.fields["duplicates"]} == {"removed"}
    assert {d["sigil"] for d in out.fields["duplicates"]} == {"KNW"}
    # File untouched.
    assert _values(f, "tasks_done") == ["1", "2", "3"]


def test_gc_rename_dry_run_previews_new_names(tmp_path: Path) -> None:
    f = _brain(tmp_path)
    out = gc_handler(
        str(f), section="$6", sigil="AUD", mode="rename", dry_run=True,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields["renamed"] == 0
    assert out.fields["would_rename"] == 3
    assert out.fields["would_remove"] == 0
    assert [d["new_name"] for d in out.fields["duplicates"]] == [
        "E_0161", "E_0162", "E_0163",
    ]
    assert {d["action"] for d in out.fields["duplicates"]} == {"renamed"}
    # File untouched — dupes still present.
    aud = _names(f, "$6/AUD:*")
    assert aud.count("E_0157") == 3
    assert aud.count("E_0158") == 2
