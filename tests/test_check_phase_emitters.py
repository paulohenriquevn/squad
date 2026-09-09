"""A phase nothing records cannot be told from a phase that was skipped.

Measured before the sweep existed: four of eight declared phases emitted nothing, and
the two silent ones were the cycle's only `required` phases. `release` was among them,
which is the verdict `cycle-maintenance.md`'s ADVANCE consumes — so ADVANCE could only
have inferred the release from files, and written `shipped` on the inference.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from check_phase_emitters import check_phase_emitters, declared_phases

_PHASES = "backlog       | required    | registers the item\nrelease       | conditional | cuts a version\n"


def _repo(tmp_path: Path, phases: str = _PHASES, skill: str = "", script: str = "") -> Path:
    (tmp_path / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "rules" / "cycle-phases.txt").write_text(phases, encoding="utf-8")
    d = tmp_path / "skills" / "doer"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(skill or "# doer\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "scripts" / "runner.py").write_text(script or "# nothing\n", encoding="utf-8")
    return tmp_path


def test_a_phase_no_one_emits_is_reported(tmp_path: Path) -> None:
    report = check_phase_emitters(_repo(tmp_path))
    assert {f.phase for f in report.findings} == {"backlog", "release"}


def test_a_cli_invocation_counts_as_an_emitter(tmp_path: Path) -> None:
    skill = "Run:\n```bash\ncycle_events.py end --cycle backlog --verdict ITEM_REGISTERED\n```\n"
    report = check_phase_emitters(_repo(tmp_path, skill=skill))
    assert [f.phase for f in report.findings] == ["release"]


def test_a_keyword_argument_counts_as_an_emitter(tmp_path: Path) -> None:
    report = check_phase_emitters(_repo(tmp_path, script='emit_phase_end(root, cycle="release")\n'))
    assert [f.phase for f in report.findings] == ["backlog"]


def test_the_requirement_column_is_carried_into_the_finding(tmp_path: Path) -> None:
    """A silent `required` phase is worse than a silent `conditional` one."""
    report = check_phase_emitters(_repo(tmp_path))
    assert next(f for f in report.findings if f.phase == "backlog").requirement == "required"


def test_where_reports_which_file_emits(tmp_path: Path) -> None:
    report = check_phase_emitters(_repo(tmp_path, script='cycle="release"\n'))
    assert report.where["release"] == ["scripts/runner.py"]


def test_a_phase_named_only_in_prose_does_not_count(tmp_path: Path) -> None:
    """"the release phase" in a sentence records nothing."""
    report = check_phase_emitters(_repo(tmp_path, skill="The release phase cuts a version.\n"))
    assert {f.phase for f in report.findings} == {"backlog", "release"}


def test_a_similar_phase_name_is_not_a_match(tmp_path: Path) -> None:
    """`--cycle release-notes` must not satisfy `release`."""
    report = check_phase_emitters(_repo(tmp_path, skill="--cycle release-notes\n"))
    assert "release" in {f.phase for f in report.findings}


def test_comments_and_blank_rows_are_skipped(tmp_path: Path) -> None:
    phases = "# a comment\n\nbacklog | required | registers\n"
    assert [p for p, _ in declared_phases(_repo(tmp_path, phases=phases))] == ["backlog"]


def test_an_absent_phases_file_declares_nothing(tmp_path: Path) -> None:
    (tmp_path / "rules").mkdir(parents=True)
    assert check_phase_emitters(tmp_path).phases == 0


@pytest.mark.parametrize("path", ["mechanisms/gates/check_phase_emitters.py", "mechanisms/cycle/cycle_events.py"])
def test_the_sweep_cannot_pass_by_reading_its_own_prose(tmp_path: Path, path: str) -> None:
    """These files name every phase while emitting for none."""
    repo = _repo(tmp_path)
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('--cycle backlog\n--cycle release\n', encoding="utf-8")
    assert len(check_phase_emitters(repo).findings) == 2


# ── the kit itself ────────────────────────────────────────────────────────────


def test_every_declared_phase_in_this_repository_has_an_emitter() -> None:
    report = check_phase_emitters(Path(__file__).resolve().parent.parent)
    assert report.findings == [], [f"{f.phase} ({f.requirement})" for f in report.findings]
