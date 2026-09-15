"""How much alignment an item needs, derived from the item.

A consumer ran the chain for three days: 93 items, 501 artefacts, 4 implementations,
0 shipped, 78 hours of cycle time per item. The alignment briefs came to 2,740 KB and
were signed by a person ZERO times — 40-50 KB each, longer than the code they describe,
which measured 40 to 250 lines across the four items that reached a branch.

`cycle-brainstorm` and `cycle-design` were already conditional. This one was not, so
deleting an unreferenced package crossed the same phases as redesigning the data plane.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import classify_alignment_depth as cd

_ITEM = """## {iid} — a title   [ ]

domain: api
repo: api
suggested_mode: {mode}
source: human
evidence: |
  {evidence}
why_now: something changed
{blocked}status: triaged
dod:
{dod}
"""


def _project(tmp_path: Path, *, iid="B-001", mode="review",
             evidence="api/internal/handler.go:41 — the retry has no ceiling",
             blocked="", dod="  - `go test ./api/... -run TestRetry` exits 0\n") -> Path:
    (tmp_path / "BACKLOG.md").write_text(
        "# Backlog\n\n## Items\n\n" + _ITEM.format(
            iid=iid, mode=mode, evidence=evidence,
            blocked=f"blocked_by: {blocked}\n" if blocked else "", dod=dod),
        encoding="utf-8")
    return tmp_path


# ── what makes an item LOCAL ────────────────────────────────────────────────

def test_one_module_with_an_executable_dod_is_local(tmp_path):
    """The 37% of a real registry that does not need a 40 KB document."""
    v = cd.classify(_project(tmp_path), "B-001")
    assert v.depth == "LOCAL"
    assert v.reasons == []


# ── what forces FULL, one signal each ───────────────────────────────────────

def test_evidence_spanning_modules_is_full(tmp_path):
    """Two readers can picture different systems when the change crosses a boundary."""
    v = cd.classify(_project(
        tmp_path,
        evidence="api/handler.go:41 and operators/reconciler.go:88 disagree"), "B-001")
    assert v.depth == "FULL"
    assert "spans 2 modules" in v.reasons[0]


def test_a_blocked_item_is_full(tmp_path):
    """Its shape depends on what lands first, so aligning it now aligns a guess."""
    v = cd.classify(_project(tmp_path, blocked="B-002"), "B-001")
    assert v.depth == "FULL"
    assert any("blocked" in r for r in v.reasons)


def test_a_dod_naming_no_command_is_full(tmp_path):
    """Work nobody can run yet is work nobody has made concrete."""
    v = cd.classify(_project(tmp_path, dod="  - the retry behaves correctly\n"), "B-001")
    assert v.depth == "FULL"
    assert any("not concrete" in r for r in v.reasons)


def test_mode_evolve_is_full(tmp_path):
    """`cycle-backlog` defines evolve as changing what the system IS."""
    v = cd.classify(_project(tmp_path, mode="evolve"), "B-001")
    assert v.depth == "FULL"


# ── the direction of the default ────────────────────────────────────────────

def test_full_is_the_default_when_signals_are_absent(tmp_path):
    """Shallower is the irreversible direction.

    A brief nobody wrote cannot be consulted later; one nobody needed only cost time.
    So an item with NO evidence at all — no modules to count — is FULL, because the
    signal is missing rather than negative.
    """
    v = cd.classify(_project(tmp_path, evidence="measured in a load test",
                             dod="  - it is faster\n"), "B-001")
    assert v.depth == "FULL"


def test_an_item_not_in_the_registry_is_not_measured(tmp_path):
    v = cd.classify(_project(tmp_path), "B-999")
    assert v.measurable is False
    assert v.depth == "FULL", "unmeasurable must not read as LOCAL"


def test_a_missing_registry_is_not_measured(tmp_path):
    v = cd.classify(tmp_path, "B-001")
    assert v.measurable is False


# ── what LOCAL keeps ────────────────────────────────────────────────────────

def test_the_local_verdict_names_what_is_kept_and_what_is_dropped(tmp_path):
    """A reader must not have to guess which half of the document survived."""
    text = cd.render(cd.classify(_project(tmp_path), "B-001"))
    assert "DROPPED" in text and "walkthrough" in text
    assert "KEPT" in text and "acceptance criteria that execute" in text


def test_exit_codes_separate_local_full_and_unmeasurable(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["x", str(_project(tmp_path)), "B-001"])
    assert cd.main() == 0
    monkeypatch.setattr(sys, "argv", ["x", str(_project(tmp_path, mode="evolve")), "B-001"])
    assert cd.main() == 1
    monkeypatch.setattr(sys, "argv", ["x", str(tmp_path / "nope"), "B-001"])
    assert cd.main() == 2
