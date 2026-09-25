"""`.tree-state` recorded the tree the SPAWNER ran in and was read as the reviewers'.

Measured 2026-09-20 on a real `/review`: the file recorded `head: a84eda52a`, the shared
checkout, while every spawned reviewer ran in a worktree at `0051d2f6b`, and
`git merge-base --is-ancestor` says that tree does NOT contain the change under review.
Two of five reviewers noticed the code looked pre-change, re-derived everything against
the right ref, and filed accurate findings. Neither was told to; the other three were not
so lucky, and nothing downstream could have told.

The comparison the consolidator makes is sound — it just answers a different question
than the one the agent prompts advertise. `capture_tree_state` proves the SPAWNER's tree
did not move; the prompts said the reviewers' tree had been recorded. One field, two
facts, and they only disagree when the reviewers run somewhere else — which is exactly
the isolation the same prompts ask for.

The kit does not create those worktrees and cannot choose where an agent runs. What it
can do is stop claiming otherwise, ask each reviewer to declare the tree it read, and
compare the two.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "first")
    return root


def _advance(root: Path, body: str) -> str:
    (root / "a.txt").write_text(body, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "second")
    return _git(root, "rev-parse", "HEAD")


def _findings(findings_dir: Path, name: str, *, head: str | None) -> None:
    findings_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"agent: {name}"]
    if head is not None:
        lines.append(f"tree_head: {head}")
    lines += ["findings:", "  - id: F1", "    severity: MINOR", "    title: something"]
    (findings_dir / f"{name}.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_the_record_names_whose_tree_it_is(repo: Path, tmp_path: Path) -> None:
    from consolidate_findings import record_tree_state

    findings = tmp_path / "findings"
    state = record_tree_state(repo, findings)

    assert state is not None
    assert state["recorded_by"] == "spawner", (
        "the record says HEAD and status and never whose tree they belong to, which is "
        "the whole of the confusion it caused"
    )
    assert Path(state["recorded_in"]).resolve() == repo.resolve()


def test_a_reviewer_on_a_tree_without_the_change_is_reported(repo: Path, tmp_path: Path) -> None:
    from consolidate_findings import check_reviewer_trees, record_tree_state

    stale = _git(repo, "rev-parse", "HEAD")
    _advance(repo, "two\n")
    findings = tmp_path / "findings"
    record_tree_state(repo, findings)
    _findings(findings, "domain-reviewer", head=stale)

    report = check_reviewer_trees(repo, findings)

    assert report is not None
    assert [r["agent"] for r in report["stale"]] == ["domain-reviewer"]


def test_a_reviewer_on_a_tree_that_contains_the_change_is_not_reported(
    repo: Path, tmp_path: Path,
) -> None:
    from consolidate_findings import check_reviewer_trees, record_tree_state

    head = _advance(repo, "two\n")
    findings = tmp_path / "findings"
    record_tree_state(repo, findings)
    _findings(findings, "domain-reviewer", head=head)

    assert check_reviewer_trees(repo, findings) is None


def test_a_reviewer_that_declares_nothing_is_named_rather_than_assumed_clean(
    repo: Path, tmp_path: Path,
) -> None:
    """Undeclared is not stale, and it is not clean either.

    Every findings file written before the templates asked for `tree_head` is in this
    class. Reporting them as stale would make every historical review dirty; reporting
    them as verified is the defect this whole item is about.
    """
    from consolidate_findings import check_reviewer_trees, record_tree_state

    findings = tmp_path / "findings"
    record_tree_state(repo, findings)
    _findings(findings, "architecture-reviewer", head=None)

    report = check_reviewer_trees(repo, findings)

    assert report is not None
    assert report["undeclared"] == ["architecture-reviewer"]
    assert report["stale"] == []


def test_a_reviewer_ahead_of_the_spawner_is_not_stale(repo: Path, tmp_path: Path) -> None:
    """Containing the change is the test, not equality.

    A reviewer whose worktree carries an extra commit still read the change under review.
    Demanding an identical SHA would report the isolation working as a defect.
    """
    from consolidate_findings import check_reviewer_trees, record_tree_state

    findings = tmp_path / "findings"
    record_tree_state(repo, findings)
    ahead = _advance(repo, "two\n")
    _findings(findings, "test-reviewer", head=ahead)

    assert check_reviewer_trees(repo, findings) is None


def test_a_head_git_cannot_resolve_is_unreadable_not_stale(repo: Path, tmp_path: Path) -> None:
    from consolidate_findings import check_reviewer_trees, record_tree_state

    findings = tmp_path / "findings"
    record_tree_state(repo, findings)
    # All digits, and unquoted in the file the helper writes: YAML hands back an
    # integer whose leading zeros are gone. Declared and unusable — which is a
    # different answer from not declared, and from a tree that lacks the change.
    _findings(findings, "wiring-reviewer", head="0" * 40)

    report = check_reviewer_trees(repo, findings)

    assert report is not None
    assert report["unresolved"] == ["wiring-reviewer"]
    assert report["stale"] == []


def test_the_templates_stop_claiming_the_reviewers_tree_was_recorded() -> None:
    """The sentence that made the record trustworthy is the one that was wrong."""
    templates = sorted(
        (Path(__file__).resolve().parent.parent / "templates").glob("agent-*-reviewer.md")
    )
    assert templates, "no reviewer templates found"
    for path in templates:
        text = path.read_text(encoding="utf-8")
        assert "records the tree state when you are spawned" not in text, (
            f"{path.name} still tells the reviewer its own tree was recorded"
        )
        assert "tree_head" in text, (
            f"{path.name} does not ask the reviewer to declare the tree it read"
        )


# ── the mechanism has to be INVOKED ──────────────────────────────────────────
#
# Half the defects this kit has fixed are a mechanism that was written, tested and never
# called. `check_reviewer_trees` passing its own unit tests proves nothing about whether
# a reviewer reading the wrong tree reaches a reader — which is bullet three of the report
# and the only bullet a human cannot compensate for by hand.

SCRIPT = _SCRIPTS / "consolidate_findings.py"


def _run(findings: Path, output: Path, repo: Path) -> dict:
    (findings / ".upstream-ok").write_text("", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--findings-dir", str(findings),
         "--output", str(output), "--slug", "fixture", "--repo-root", str(repo)],
        capture_output=True, text=True, check=False,
    )
    if "{" not in result.stdout:
        return {}
    try:
        return json.loads(result.stdout[result.stdout.index("{"):])
    except json.JSONDecodeError:
        return {}


def test_a_stale_reviewer_reaches_the_json_a_gate_reads(repo: Path, tmp_path: Path) -> None:
    from consolidate_findings import record_tree_state

    stale = _git(repo, "rev-parse", "HEAD")
    _advance(repo, "two\n")
    findings = tmp_path / "findings"
    record_tree_state(repo, findings)
    _findings(findings, "domain-reviewer", head=stale)

    payload = _run(findings, tmp_path / "report.md", repo)

    assert [r["agent"] for r in payload["reviewer_trees"]["stale"]] == ["domain-reviewer"]


def test_a_stale_reviewer_is_named_above_the_findings_not_below(
    repo: Path, tmp_path: Path,
) -> None:
    from consolidate_findings import record_tree_state

    stale = _git(repo, "rev-parse", "HEAD")
    _advance(repo, "two\n")
    findings = tmp_path / "findings"
    record_tree_state(repo, findings)
    _findings(findings, "domain-reviewer", head=stale)
    output = tmp_path / "report.md"

    _run(findings, output, repo)

    body = output.read_text(encoding="utf-8")
    warning = body.index("read a tree that does not contain")
    assert warning < body.index("## Findings summary by severity"), (
        "a reader who learns this after the findings has already believed them"
    )


def test_a_clean_run_stays_silent(repo: Path, tmp_path: Path) -> None:
    """The control. A signal that always fires is the same as no signal."""
    from consolidate_findings import record_tree_state

    head = _advance(repo, "two\n")
    findings = tmp_path / "findings"
    record_tree_state(repo, findings)
    _findings(findings, "domain-reviewer", head=head)

    payload = _run(findings, tmp_path / "report.md", repo)

    assert "reviewer_trees" not in payload


def _consolidate(repo: Path, findings: Path, tmp_path: Path, capsys) -> tuple[int, dict, str]:
    import consolidate_findings

    argv = ["consolidate_findings.py", "--findings-dir", str(findings),
            "--output", str(tmp_path / "report.md"), "--slug", "demo",
            "--repo-root", str(repo)]
    old, sys.argv = sys.argv, argv
    try:
        code = consolidate_findings.main()
    finally:
        sys.argv = old
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


def test_a_review_whose_reviewer_read_a_stale_tree_is_refused(
    repo: Path, tmp_path: Path, capsys,
) -> None:
    """A reviewer that read a tree without the change reviewed other code. Reporting it
    above the findings still let the verdict read READY_TO_MERGE, so a reviewer who did
    not notice would have signed off on code it never opened. Measured on a consumer
    2026-09-20: every spawned reviewer ran at a commit that did not contain the change,
    and two of five noticed by comparing SHAs by eye (#148)."""
    stale = _git(repo, "rev-parse", "HEAD")
    under_review = _advance(repo, "two\n")
    findings = tmp_path / "findings"
    from consolidate_findings import record_tree_state
    record_tree_state(repo, findings)
    _findings(findings, "domain-reviewer", head=stale)

    code, summary, err = _consolidate(repo, findings, tmp_path, capsys)

    assert code != 0
    assert summary["verdict"] == "INVALID"
    assert "domain-reviewer" in err
    assert under_review[:12] in err


def test_a_reviewer_that_declares_no_tree_does_not_refuse_the_review(
    repo: Path, tmp_path: Path, capsys,
) -> None:
    """Every findings file written before the templates asked for `tree_head` declares
    nothing. Refusing those would make every historical review unreadable."""
    findings = tmp_path / "findings"
    from consolidate_findings import record_tree_state
    record_tree_state(repo, findings)
    _findings(findings, "architecture-reviewer", head=None)

    _, summary, err = _consolidate(repo, findings, tmp_path, capsys)

    # The minimal fixture draws other findings (a short roster), so only the refusal
    # this test is about is asserted absent.
    assert summary["verdict"] != "INVALID"
    assert "stale tree" not in err
