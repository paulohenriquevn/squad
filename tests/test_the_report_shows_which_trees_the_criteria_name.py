"""A brief can score 34/34 while every path its criteria name lives in another repository.

Two gates, each correct in its own scope, and the space between them (#177):

- `route_domain.py` checks the DECLARED `repo:`, never the paths criteria name. The declared
  value routes, so nothing refuses.
- `score_alignment.py` grades a criterion executable when it names something that RUNS, not
  something that EXISTS — deliberate and documented at `:101-115`, because a plan describes
  files not yet created and resolving them would reject every legitimate plan.

Measured on a consumer: 17 of 17 rubric criteria green, and the 14 paths its acceptance
criteria named lived in a sibling git checkout. Hours of brief and plan for work the registry
cannot execute. `grep -rln 'acceptance_criteria\\|criteria' mechanisms/gates/*.py` returns
nothing: no gate reads criteria at all.

WHAT THIS DOES AND DOES NOT DO. It does not judge, and it is not a gate. The scorer receives
only the brief — it has no access to the item's `repo:`, which lives in `BACKLOG.md` — so a
comparison would need new plumbing, and a hard cap would fire on honest work (a criterion
legitimately names a config at an umbrella root or a shared test; `code-quality-golden-rule.md
§ 4.1` argues that a gate firing on ordinary work is one somebody switches off).

So it SHOWS. The report lists the top-level trees the criteria name, with counts. A reader who
filed the item against `packages/theo` and sees `packages/ui (14)` knows immediately, before
writing the plan — which is the sentence that was missing. No new blocking surface, no new gate
in the chain, no contract change, and nothing new asked of the caller.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "skills" / "plan-alignment" / "scripts"))

HEAD = "# Alignment: X\n\n## Problem\n" + ("word " * 40) + "\n"


def _brief(tmp_path: Path, criteria: str) -> Path:
    p = tmp_path / "brief.md"
    p.write_text(HEAD + "\n## Acceptance Criteria\n" + criteria, encoding="utf-8")
    return p


def _score(path: Path):
    from score_alignment import score_alignment
    return score_alignment(path)


def test_the_trees_the_criteria_name_are_reported(tmp_path: Path) -> None:
    report = _score(_brief(tmp_path,
        "- **AC-001** — `bash -c 'npx vitest run packages/ui/tests/a.test.ts'` passes\n"
        "- **AC-002** — `bash -c 'npx vitest run packages/ui/tests/b.test.ts'` passes\n"
        "- **AC-003** — `bash -c 'node scripts/probe.mjs'` prints 1\n"))

    trees = dict(report.criteria_trees)
    assert trees.get("packages/ui") == 2, trees
    assert trees.get("scripts") == 1, trees


def test_a_brief_naming_one_tree_reports_one(tmp_path: Path) -> None:
    """The control: without it, a reader cannot tell a clean brief from an unparsed one."""
    report = _score(_brief(tmp_path,
        "- **AC-001** — `bash -c 'pytest tests/test_a.py'` passes\n"
        "- **AC-002** — `bash -c 'pytest tests/test_b.py'` passes\n"))

    assert dict(report.criteria_trees) == {"tests": 2}, report.criteria_trees


def test_criteria_with_no_paths_report_nothing(tmp_path: Path) -> None:
    """A criterion may name only a command. An empty map is a fact, not a failure."""
    report = _score(_brief(tmp_path, "- **AC-001** — `bash -c 'make check'` exits 0\n"))

    assert report.criteria_trees == ()


def test_two_packages_in_one_brief_appear_side_by_side(tmp_path: Path) -> None:
    """The motivating case, and the one two earlier rules failed.

    Reported on a consumer's item filed as `repo: packages/theo` whose criteria named
    `packages/ui`. Collapsing to the first segment printed `packages`, identical for both, so
    the reader saw nothing wrong; collapsing on disagreement printed `packages` too, because
    the criteria named BOTH. The mismatch has to be the line itself.
    """
    report = _score(_brief(tmp_path,
        "- **AC-001** — `bash -c 'npx vitest run packages/ui/tests/a.test.ts'`\n"
        "- **AC-002** — `bash -c 'npx vitest run packages/ui/tests/b.test.ts'`\n"
        "- **AC-003** — `bash -c 'npx vitest run packages/theo/tests/c.test.ts'`\n"))

    trees = dict(report.criteria_trees)
    assert trees == {"packages/ui": 2, "packages/theo": 1}, trees


def test_a_flag_is_not_mistaken_for_a_path(tmp_path: Path) -> None:
    """`--cov=mechanisms` and `-k name/other` are not trees; counting them would be noise."""
    report = _score(_brief(tmp_path,
        "- **AC-001** — `bash -c 'pytest --cov=mechanisms -p no:cacheprovider tests/x.py'`\n"))

    assert dict(report.criteria_trees) == {"tests": 1}, report.criteria_trees


def test_the_line_reaches_the_rendered_report(tmp_path: Path, capsys) -> None:
    """In the output a person reads, not only in the data behind it."""
    from score_alignment import main
    path = _brief(tmp_path,
        "- **AC-001** — `bash -c 'npx vitest run packages/ui/tests/a.test.ts'` passes\n")

    main([str(path)])

    out = capsys.readouterr().out
    assert "packages" in out and "criteria name paths" in out, out[-1200:]
