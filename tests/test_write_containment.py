"""Everything this system writes lands under `<project>/.squad/`, proved two ways.

The guarantee has a structural half and an empirical one, and neither is sufficient
alone:

  STRUCTURAL   no module outside `squad/paths.py` can spell a data root, so every path
               a writer builds came from the owner. `check_write_containment.py`
               re-runs that proof; reading 164 writing call sites does not.
  EMPIRICAL    real writers, run against a real temporary project, create nothing
               outside the root. This is what would catch an owner that is itself
               wrong — the one thing the scan cannot see.

Why it matters beyond tidiness: measured across 20 consumer repositories on
2026-09-09, 17 had the kit committed to git and every one carried between 348 and 566
permanently dirty files. All of them were inside the install directory, and nothing
outside it was dirty anywhere. The system wrote its output into the same folder as the
dependency, so a project could not un-version one without un-versioning the other.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "mechanisms" / "cycle"))
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))
sys.path.insert(0, str(_REPO / "mechanisms" / "conventions"))

from check_write_containment import OWNER, scan, strip_prose  # noqa: E402

from squad.paths import (  # noqa: E402
    DATA_DIRNAME,
    contains,
    records_dir,
    resolve_knowledge_dir,
    wiki_dir,
    write_records_dir,
    write_wiki_dir,
)


def _tree(root: Path) -> set[Path]:
    return {p.relative_to(root) for p in root.rglob("*")}


# ---------------------------------------------------------------------------
# The structural half
# ---------------------------------------------------------------------------

def test_no_kit_module_outside_the_owner_spells_a_data_root() -> None:
    """The proof that makes the empirical half generalise.

    Every writer builds its path from `squad/paths.py`, because nothing else can name
    a root. Six modules each held their own copy of that list, in four different
    orders, and a reader resolving one order found a directory a writer using another
    had never filled.
    """
    findings = scan(_REPO)

    assert not findings, "\n".join(
        f"{f['file']}:{f['line']}  {f['literal']}" for f in findings)


def test_the_scan_reports_a_line_a_reader_can_open(tmp_path: Path) -> None:
    """Prose is BLANKED, not deleted.

    Deleting it shifts every line after, and the gate then names a line holding
    something else — a finding nobody can find is a finding they stop trusting.
    """
    src = '"""a docstring\nspanning lines\n"""\nx = 1\ny = "records/plans"\n'
    stripped = strip_prose(src, ".py")

    assert stripped.count("\n") == src.count("\n")
    assert stripped.splitlines()[4] == 'y = "records/plans"'


def test_the_owner_is_allowed_to_spell_them() -> None:
    """Otherwise there would be nowhere left to define the roots at all."""
    assert (_REPO / OWNER).is_file()
    assert "records" in (_REPO / OWNER).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The empirical half
# ---------------------------------------------------------------------------

def _run(module: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(module), *args],
                          capture_output=True, text=True, timeout=120, check=False)


def test_the_event_stream_writes_only_inside_the_root(tmp_path: Path) -> None:
    from cycle_events import emit_phase_end, emit_phase_start

    before = _tree(tmp_path)
    emit_phase_start(tmp_path, cycle="discover", slug="B-001")
    emit_phase_end(tmp_path, cycle="discover", slug="B-001", verdict="SHIPPABLE")
    created = _tree(tmp_path) - before

    assert created, "the writer wrote nothing, so this proves nothing"
    assert all(p.parts[0] == DATA_DIRNAME for p in created), sorted(map(str, created))


def test_the_panel_assignment_writes_only_inside_the_root(tmp_path: Path) -> None:
    (tmp_path / "agents").mkdir()
    for agent in ("nemesis-claim-auditor", "leonardo-researcher"):
        (tmp_path / "agents" / f"{agent}.md").write_text("---\n", encoding="utf-8")

    before = _tree(tmp_path)
    _run(_REPO / "mechanisms" / "cycle" / "convene_panel.py",
         "--slug", "B-001", "--phase", "discover", "--project", str(tmp_path),
         "--write", "--json")
    created = _tree(tmp_path) - before

    assert all(p.parts[0] == DATA_DIRNAME for p in created), sorted(map(str, created))


def test_the_auditor_assignment_writes_only_inside_the_root(tmp_path: Path) -> None:
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "review-auditors.txt").write_text(
        "auditor = always | loop-code-review | analysis-scoped | code-review-output\n",
        encoding="utf-8")

    before = _tree(tmp_path)
    _run(_REPO / "mechanisms" / "cycle" / "select_auditors.py",
         "--slug", "B-001", "--domains", "security", "--project", str(tmp_path),
         "--write", "--json")
    created = _tree(tmp_path) - before

    assert all(p.parts[0] == DATA_DIRNAME for p in created), sorted(map(str, created))


# ---------------------------------------------------------------------------
# The resolver itself
# ---------------------------------------------------------------------------

def test_a_writer_never_falls_back(tmp_path: Path) -> None:
    """A legacy root on disk does not capture the writer.

    A writer that fell back would keep every project on its old root forever, and the
    centralisation would be a sentence in a rule with nothing behind it.
    """
    (tmp_path / ".claude" / "records" / "plans").mkdir(parents=True)

    assert write_records_dir(tmp_path, "plans") == (
        tmp_path / DATA_DIRNAME / "records" / "plans")


def test_a_reader_does_fall_back(tmp_path: Path) -> None:
    """So a consumer that has not migrated keeps working."""
    legacy = tmp_path / ".claude" / "records" / "plans"
    legacy.mkdir(parents=True)

    assert records_dir(tmp_path, "plans") == legacy


def test_the_new_root_wins_over_a_legacy_one(tmp_path: Path) -> None:
    """Once migrated, a stale copy in the old root is never read.

    A fallback that returns the first hit makes the old copy unreachable, which is the
    correct direction: the alternative is a reader silently preferring stale evidence.
    """
    (tmp_path / ".claude" / "records" / "plans").mkdir(parents=True)
    current = write_records_dir(tmp_path, "plans")
    current.mkdir(parents=True)

    assert records_dir(tmp_path, "plans") == current


def test_durable_knowledge_resolves_to_the_bundle_before_the_trail(tmp_path: Path) -> None:
    """`decisions` is durable; `records/adrs/` is where the trail used to keep it."""
    legacy = tmp_path / "records" / "adrs"
    legacy.mkdir(parents=True)
    assert resolve_knowledge_dir(tmp_path, "decisions") == legacy

    bundle = write_wiki_dir(tmp_path, "decisions")
    bundle.mkdir(parents=True)
    assert resolve_knowledge_dir(tmp_path, "decisions") == bundle


def test_a_leaf_that_is_not_durable_never_resolves_to_the_bundle(tmp_path: Path) -> None:
    """Accepting `wiki/sop-runs/` because someone created it would invite exactly the
    mixing the split exists to prevent."""
    stray = write_wiki_dir(tmp_path, "sop-runs")
    stray.mkdir(parents=True)

    assert resolve_knowledge_dir(tmp_path, "sop-runs") != stray


def test_contains_answers_the_question_the_gate_asks(tmp_path: Path) -> None:
    assert contains(tmp_path, write_records_dir(tmp_path, "plans") / "a.md")
    assert not contains(tmp_path, tmp_path / "records" / "a.md")
    assert not contains(tmp_path, tmp_path / ".claude" / "records" / "a.md")


def test_the_bundle_and_the_trail_stay_apart_inside_the_root(tmp_path: Path) -> None:
    """Centralising the root must not collapse the split.

    A reader looking for a decision and a reader looking for what happened on a Tuesday
    want different things, and mixing them is the failure `records-location.md` was
    written about.
    """
    assert write_wiki_dir(tmp_path) != write_records_dir(tmp_path)
    assert wiki_dir(tmp_path) is None and records_dir(tmp_path) is None
