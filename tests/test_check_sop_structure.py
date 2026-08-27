"""A SOP says what to do; the gate is that it also says where it stops applying.

WHAT THIS CHECKS, AND WHY EACH ONE EARNS ITS PLACE
---------------------------------------------------
`rules/sop-schema.md` splits the static script from the judgement that runs it.
This checker enforces the half a text scan can enforce — the script's shape —
and refuses to pretend it can judge the other half.

| Finding | What it catches |
|---|---|
| `step_without_imperative` | "the branch should be workspace" — a state, not an instruction |
| `decision_branch_without_exit` | a branch the tree opens and never closes |
| `missing_escalation` | a procedure asserting reality never departs from it |
| `competency_without_verification` | a training matrix with the training left out |
| `sop_stale` | past its own review interval |
| `malformed_frontmatter` | no owner, no version, no review date |

THE ONE THAT MATTERS MOST
-------------------------
`missing_escalation`. Every other finding is about a badly written script; this
one is about a script that claims to be complete. A SOP with no escalation
section says the world never differs from the assumption — false of every
procedure ever written — and it is precisely that claim that converts a
deviation into an undocumented improvisation, because the document offered
nowhere to put it.

WHAT IT DELIBERATELY CANNOT DO
------------------------------
It does not check whether the steps are the RIGHT steps, whether the named
`standard:` is actually satisfied, or whether an escalation route is sensible.
Those are judgement, and a checker asserting them would be the fabricated
confidence this ecosystem caps plans at 49 for. It checks shape, and says so.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_sop_structure import check_sop_structure  # noqa: E402

_FRONTMATTER = """\
---
sop: demo-procedure
version: 1.0.0
owner: kit maintainer
standard: _none_
last_reviewed: 2026-08-20
review_interval_days: 180
---
"""

_BODY = """
# Port a fix between the two kits

## Purpose
One sentence saying why this exists.

## Prerequisites
- [ ] The working branch is `workspace` — `git branch --show-current`.

## Steps
1. **Verify** the suite is green — `bash scripts/run_slice_tests.sh`.
2. **Copy** the script into the sibling kit.

## Decisions
```mermaid
flowchart TD
    A[Gate failed] --> B{Mechanism exists here?}
    B -->|yes| C[Name it in the rule]
    B -->|no| D[Mark it not mechanized]
```

## Escalation
- **The named script does not exist in this kit** → stop, and mark the gate not
  mechanized rather than citing a module from the other repository.

## Competencies
| Competency | Who may perform | How it is verified |
|---|---|---|
| Reading a gate verdict | anyone on the kit | ran `/code-quality` end to end once |
"""


def _sop(tmp_path: Path, body: str = _FRONTMATTER + _BODY, name: str = "demo.md") -> Path:
    sops = tmp_path / "knowledge-base" / "sops"
    sops.mkdir(parents=True, exist_ok=True)
    (sops / name).write_text(body, encoding="utf-8")
    return tmp_path


def _kinds(report) -> list[str]:
    return sorted({f.kind for f in report.findings})


# ---------------------------------------------------------------------------
# The shape that passes
# ---------------------------------------------------------------------------

def test_a_wellformed_sop_produces_no_finding(tmp_path: Path) -> None:
    root = _sop(tmp_path)

    report = check_sop_structure(root, today="2026-08-27")

    assert report.findings == [], [f.detail for f in report.findings]
    assert report.sops_read == 1


def test_the_counts_are_reported_even_when_clean(tmp_path: Path) -> None:
    """A checker that says PASS without saying how much it inspected is the
    empty gate this ecosystem refuses everywhere else."""
    root = _sop(tmp_path)

    report = check_sop_structure(root, today="2026-08-27")

    assert report.steps_read == 2
    assert report.branches_read == 2


# ---------------------------------------------------------------------------
# Imperative voice — competency 1
# ---------------------------------------------------------------------------

def test_a_step_describing_a_state_is_reported(tmp_path: Path) -> None:
    """"The branch should be workspace" is a description. Nobody performs a
    description at 3am."""
    body = _FRONTMATTER + _BODY.replace(
        "1. **Verify** the suite is green — `bash scripts/run_slice_tests.sh`.",
        "1. The suite should be green before continuing.",
    )
    root = _sop(tmp_path, body)

    report = check_sop_structure(root, today="2026-08-27")

    assert "step_without_imperative" in _kinds(report)
    assert "should be green" in report.findings[0].detail


def test_a_passive_step_is_reported(tmp_path: Path) -> None:
    body = _FRONTMATTER + _BODY.replace(
        "2. **Copy** the script into the sibling kit.",
        "2. The script is copied into the sibling kit by the maintainer.",
    )
    root = _sop(tmp_path, body)

    assert "step_without_imperative" in _kinds(check_sop_structure(root, today="2026-08-27"))


@pytest.mark.parametrize("opener", ["**Run**", "Run", "**Verify**", "Stop"])
def test_an_imperative_opener_passes_bold_or_not(tmp_path: Path, opener: str) -> None:
    """Bold is the house style, not the contract. Enforcing the asterisks would
    fail a correct instruction for its formatting."""
    body = _FRONTMATTER + _BODY.replace(
        "1. **Verify** the suite is green — `bash scripts/run_slice_tests.sh`.",
        f"1. {opener} the suite — `bash scripts/run_slice_tests.sh`.",
    )
    root = _sop(tmp_path, body)

    assert "step_without_imperative" not in _kinds(check_sop_structure(root, today="2026-08-27"))


# ---------------------------------------------------------------------------
# Decision branches — competency 2
# ---------------------------------------------------------------------------

def test_a_branch_that_leads_nowhere_is_reported(tmp_path: Path) -> None:
    """The SOP analogue of `phase_ran_undeclared`: the diagram looks complete and
    the path is not there."""
    body = _FRONTMATTER + _BODY.replace(
        "    B -->|no| D[Mark it not mechanized]\n", ""
    )
    root = _sop(tmp_path, body)

    report = check_sop_structure(root, today="2026-08-27")

    assert "decision_branch_without_exit" in _kinds(report)
    detail = next(f.detail for f in report.findings if f.kind == "decision_branch_without_exit")
    assert "B" in detail


def test_a_sop_with_no_decisions_section_is_fine(tmp_path: Path) -> None:
    """Not every procedure branches. Demanding a diagram from a linear procedure
    produces a diagram drawn to satisfy a checker."""
    root = _sop(tmp_path, "".join([
        _FRONTMATTER,
        _BODY.split("## Decisions")[0],
        "## Escalation\n- **Anything unexpected** → ask the owner.\n\n",
        "## Competencies\n| Competency | Who may perform | How it is verified |\n|---|---|---|\n"
        "| Running it | maintainer | did it once with review |\n",
    ]))

    assert "decision_branch_without_exit" not in _kinds(check_sop_structure(root, today="2026-08-27"))


# ---------------------------------------------------------------------------
# Escalation — the SOP/skill boundary
# ---------------------------------------------------------------------------

def test_a_sop_without_escalation_is_reported(tmp_path: Path) -> None:
    """The finding this checker exists for.

    Every other one is about a badly written script. This one is about a script
    claiming the world never departs from it — and that claim is what turns a
    deviation into an improvisation nobody records, because the document offered
    nowhere to put it.
    """
    body = _FRONTMATTER + _BODY.split("## Escalation")[0] + (
        "## Competencies\n| Competency | Who may perform | How it is verified |\n|---|---|---|\n"
        "| Running it | maintainer | did it once |\n"
    )
    root = _sop(tmp_path, body)

    assert "missing_escalation" in _kinds(check_sop_structure(root, today="2026-08-27"))


def test_an_empty_escalation_section_counts_as_missing(tmp_path: Path) -> None:
    """A heading with nothing under it satisfies a grep and answers no one."""
    body = _FRONTMATTER + _BODY.replace(
        "- **The named script does not exist in this kit** → stop, and mark the gate not\n"
        "  mechanized rather than citing a module from the other repository.",
        "_To be completed._",
    )
    root = _sop(tmp_path, body)

    assert "missing_escalation" in _kinds(check_sop_structure(root, today="2026-08-27"))


def test_an_escalation_entry_must_name_a_condition_and_an_action(tmp_path: Path) -> None:
    """"Escalate if needed" names neither what to watch for nor what to do."""
    body = _FRONTMATTER + _BODY.replace(
        "- **The named script does not exist in this kit** → stop, and mark the gate not\n"
        "  mechanized rather than citing a module from the other repository.",
        "- Escalate if needed.",
    )
    root = _sop(tmp_path, body)

    assert "escalation_without_route" in _kinds(check_sop_structure(root, today="2026-08-27"))


# ---------------------------------------------------------------------------
# Competencies — competency 4
# ---------------------------------------------------------------------------

def test_a_competency_without_verification_is_reported(tmp_path: Path) -> None:
    body = _FRONTMATTER + _BODY.replace(
        "| Reading a gate verdict | anyone on the kit | ran `/code-quality` end to end once |",
        "| Reading a gate verdict | anyone on the kit |  |",
    )
    root = _sop(tmp_path, body)

    assert "competency_without_verification" in _kinds(check_sop_structure(root, today="2026-08-27"))


# ---------------------------------------------------------------------------
# Version control and freshness — competency 3
# ---------------------------------------------------------------------------

def test_a_sop_past_its_review_interval_is_reported(tmp_path: Path) -> None:
    """Measurement decay, in the schema's own words: the document keeps being
    followed after it stopped describing the thing."""
    root = _sop(tmp_path)

    report = check_sop_structure(root, today="2027-08-27")

    assert "sop_stale" in _kinds(report)
    assert "180" in next(f.detail for f in report.findings if f.kind == "sop_stale")


@pytest.mark.parametrize("field", ["owner", "version", "last_reviewed"])
def test_a_missing_required_frontmatter_field_is_reported(tmp_path: Path, field: str) -> None:
    body = "\n".join(
        line for line in (_FRONTMATTER + _BODY).splitlines()
        if not line.startswith(f"{field}:")
    )
    root = _sop(tmp_path, body)

    report = check_sop_structure(root, today="2026-08-27")

    assert "malformed_frontmatter" in _kinds(report)
    assert field in next(f.detail for f in report.findings if f.kind == "malformed_frontmatter")


def test_an_owner_that_names_nobody_is_reported(tmp_path: Path) -> None:
    """"the team" cannot be asked a question. An owner is someone a reader can
    reach when the procedure fails them."""
    body = (_FRONTMATTER + _BODY).replace("owner: kit maintainer", "owner: the team")
    root = _sop(tmp_path, body)

    assert "owner_names_nobody" in _kinds(check_sop_structure(root, today="2026-08-27"))


# ---------------------------------------------------------------------------
# Sweeping
# ---------------------------------------------------------------------------

def test_a_project_with_no_sops_reports_nothing_rather_than_everything(tmp_path: Path) -> None:
    (tmp_path / "knowledge-base").mkdir(parents=True)

    report = check_sop_structure(tmp_path, today="2026-08-27")

    assert report.findings == []
    assert report.sops_read == 0


def test_both_install_layouts_are_swept(tmp_path: Path) -> None:
    sops = tmp_path / ".claude" / "knowledge-base" / "sops"
    sops.mkdir(parents=True)
    (sops / "demo.md").write_text(_FRONTMATTER + _BODY, encoding="utf-8")

    assert check_sop_structure(tmp_path, today="2026-08-27").sops_read == 1


def test_the_cli_exits_nonzero_on_a_finding(tmp_path: Path) -> None:
    import subprocess

    body = _FRONTMATTER + _BODY.split("## Escalation")[0]
    root = _sop(tmp_path, body)

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_sop_structure.py"),
         "--project-root", str(root)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 1
    assert "missing_escalation" in result.stdout


def test_this_repository_has_structurally_sound_sops() -> None:
    """The gate turned on its own SOPs. If the kit writes procedures it does not
    hold to the schema, the schema is decoration."""
    report = check_sop_structure(REPO_ROOT)

    assert report.findings == [], "\n".join(
        f"{f.sop}: [{f.kind}] {f.detail}" for f in report.findings
    )


def test_okf_reserved_filenames_are_not_concepts(tmp_path: Path) -> None:
    """`index.md` and `log.md` are navigation and history, never procedures.

    Found the moment the SOPs moved into an OKF bundle: the sweep read the
    bundle's own `index.md` as a malformed SOP and reported three findings
    against a file that is correct by the spec. A checker that fails on correct
    input is the false positive this ecosystem treats as worse than no checker.
    """
    sops = tmp_path / "wiki" / "sops"
    sops.mkdir(parents=True)
    (sops / "index.md").write_text("# Operating procedures\n\n- a listing\n", encoding="utf-8")
    (sops / "log.md").write_text("# Change log\n\n## 2026-08-27\n\n**Creation**\n", encoding="utf-8")
    (sops / "real.md").write_text(
        "---\ntype: SOP\nsop: real\nversion: 1.0.0\nowner: someone\n"
        "last_reviewed: 2026-08-20\n---\n\n"
        "## Steps\n1. **Run** it.\n\n## Escalation\n- **It breaks** → ask.\n",
        encoding="utf-8",
    )

    report = check_sop_structure(tmp_path, today="2026-08-27")

    assert report.sops_read == 1, "only the concept is a SOP"
    assert report.findings == []
