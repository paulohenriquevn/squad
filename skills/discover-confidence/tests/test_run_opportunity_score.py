"""End-to-end tests for run_opportunity_score.py — verifies scorer integration."""
from __future__ import annotations

import sys as _s
from pathlib import Path as _P

for _up in _P(__file__).resolve().parents:
    if (_up / "squad" / "paths.py").is_file():
        _s.path.insert(0, str(_up))
        break
import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from squad.paths import write_records_dir  # noqa: E402

SCRIPT = Path(__file__).parent.parent / "scripts" / "run_opportunity_score.py"


def _run(opportunity_path: Path, project_root: Path) -> tuple[int, dict]:
    result = subprocess.run(  # noqa: PLW1510
        [sys.executable, str(SCRIPT), str(opportunity_path), "--no-warn"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {"raw_stdout": result.stdout, "stderr": result.stderr}
    return result.returncode, data


@pytest.fixture
def staged(project_root: Path):
    """Write an opportunity inside the repo so the project root resolves to it.

    Pointer resolution walks up from the artifact, so an artifact parked in /tmp would
    resolve every repo-relative pointer as fabricated.
    """
    written: list[Path] = []

    # Cross-repo detection reads the project's routing table. This repository ships
    # it EMPTY on purpose (`agents/README.md` records what shipping a populated one
    # cost an adopter), so an end-to-end test of the ADR cap has to provide one.
    # Never overwrite a real table: a consumer running this suite owns theirs.
    table = project_root / "rules" / "domain-routing.txt"
    borrowed = table.read_text(encoding="utf-8") if table.is_file() else None
    if borrowed is None or not [
        ln for ln in borrowed.splitlines() if ln.strip() and not ln.startswith("#")
    ]:
        table.parent.mkdir(parents=True, exist_ok=True)
        table.write_text(
            "contracts | contracts | agents/contracts.md\n"
            "platform  | control-plane, cli-tool | agents/platform.md\n",
            encoding="utf-8",
        )
        restore = borrowed
    else:
        restore = ...  # a real table: leave it exactly as found

    def _write(name: str, content: str) -> Path:
        directory = write_records_dir(project_root, "discoveries") / "opportunities"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
        return path

    yield _write

    for path in written:
        path.unlink(missing_ok=True)

    if restore is not ...:
        if restore is None:
            table.unlink(missing_ok=True)
        else:
            table.write_text(restore, encoding="utf-8")


def test_a_structurally_perfect_opportunity_is_held_until_the_panel_sits(
    good_opportunity: Path, project_root: Path
) -> None:
    """Structure alone no longer advances a document.

    The score is perfect and the verdict is still not SHIPPABLE, because
    `rules/review-panel.txt` gates DISCOVER on 2 of 3 signed approvals and no panel
    has judged this one. `AWAITING_REVIEW` is the existing token for exactly this — "the structure is
    complete and the judgement has not been made; not a failure and not a pass" — so the
    author is NOT sent to rewrite a document nobody found fault with. It is deliberately
    NOT `ITEM_IN_FLIGHT`, which means a panel could not convene AT ALL: "nobody has
    reviewed this yet" and "nobody can review it here" take different actions.

    The score is deliberately untouched: the panel gates the verdict, never the
    number, because "this document is weak" and "nobody has reviewed it" take
    opposite actions.
    """
    rc, data = _run(good_opportunity, project_root)

    assert data["final_score_after_caps"] >= 90
    assert data["hard_caps_triggered"] == []
    assert data["verdict"] == "AWAITING_REVIEW"
    assert data["panel"]["status"] == "no_record"
    assert rc == 0, f"held is not a failure of the run: {rc}"


def test_the_panel_carries_a_good_opportunity_to_shippable(
    good_opportunity: Path, project_root: Path, tmp_path: Path
) -> None:
    """The other side: convened, approved, and the structural verdict stands."""
    slug = good_opportunity.stem.replace("-opportunity", "")
    # Resolve exactly as the gate does: `.claude/records` wins where it exists.
    base = write_records_dir(project_root)
    panels = base / "panels"
    panels.mkdir(parents=True, exist_ok=True)
    assignment = panels / f"{slug}-discover.assignment.json"
    record = panels / f"{slug}-discover.json"
    why = ("checked every pointer in corner one against the tree at the cited revision "
           "and the conclusion follows from what the evidence actually shows")
    try:
        assignment.write_text(json.dumps(
            {"assigned": ["nemesis-claim-auditor", "leonardo-researcher",
                          "judge-codex:discover-judge"]}), encoding="utf-8")
        record.write_text(json.dumps({
            "slug": slug, "phase": "discover", "artifact": str(good_opportunity),
            "author": "daedalus-tech-lead",
            "votes": [
                {"reviewer": "nemesis-claim-auditor", "model": "claude-opus-5",
                 "verdict": "approve", "reason": why},
                {"reviewer": "leonardo-researcher", "model": "claude-sonnet-5",
                 "verdict": "approve", "reason": why},
                {"reviewer": "judge-codex:discover-judge", "model": "gpt-5-codex",
                 "verdict": "return", "reason": why},
            ]}), encoding="utf-8")

        rc, data = _run(good_opportunity, project_root)

        assert data["panel"]["status"] == "approved"
        assert data["verdict"] == "SHIPPABLE"
        assert rc == 0
    finally:
        assignment.unlink(missing_ok=True)
        record.unlink(missing_ok=True)


def test_fabricated_evidence_is_invalid(good_opportunity: Path, staged) -> None:
    corrupted = staged(
        "test-fabricated-opportunity.md",
        good_opportunity.read_text(encoding="utf-8-sig")
        # Deliberately NOT under rules/: check_xrefs scans .py files for `rules/...`
        # references and would flag this intentional non-existent path as a broken xref.
        + "\n\nBogus pointer: `docs/this-file-does-not-exist-xyz.md:99`\n",
    )
    rc, data = _run(corrupted, corrupted.parents[4])
    assert rc == 1, f"Expected exit 1 (INVALID), got {rc}: {data}"
    assert data["verdict"] == "INVALID"
    assert "fabricated_evidence" in data["hard_caps_triggered"]
    assert data["final_score_after_caps"] <= 49.0


def test_pointer_past_end_of_file_is_invalid(good_opportunity: Path, staged) -> None:
    """A real file cited at a line it does not have caps the score just like a fake path."""
    corrupted = staged(
        "test-stale-pointer-opportunity.md",
        good_opportunity.read_text(encoding="utf-8-sig")
        + "\n\nStale pointer: `rules/current-constraint.md:99999`\n",
    )
    rc, data = _run(corrupted, corrupted.parents[4])
    assert rc == 1
    assert "fabricated_evidence" in data["hard_caps_triggered"]


def test_missing_corner_is_invalid(staged) -> None:
    path = staged(
        "test-missing-corner-opportunity.md",
        "# Opportunity: Test\n\n"
        "**Item:** B-002\n"
        "**Repo:** squad\n"
        "**Mode:** review\n\n"
        "## Context\n\nText.\n\n"
        # Corner 1 — Evidence MISSING
        "## Corner 2 — Constraint Relation\n\nReal content here, well past the threshold "
        "for a populated corner section.\n\n"
        "## Corner 3 — Blast Radius\n\nReal content here, well past the threshold for a "
        "populated corner section.\n\n"
        "## Corner 4 — Verification\n\nReal content here, well past the threshold for a "
        "populated corner section.\n\n"
        "## Recommendation\n\n- Do X\n",
    )
    rc, data = _run(path, path.parents[4])
    assert rc == 1, f"Expected exit 1 (INVALID), got {rc}: {data}"
    assert data["verdict"] == "INVALID"
    assert "empty_corner_evidence" in data["hard_caps_triggered"]


def test_cross_repo_without_adr_is_capped(staged) -> None:
    """Exercises the conditional ADR cap end-to-end, not just in the unit."""
    path = staged(
        "test-cross-repo-opportunity.md",
        "# Opportunity: Test\n\n"
        "**Item:** B-003\n"
        "**Repo:** contracts\n"
        "**Mode:** review\n\n"
        "## Context\n\nText.\n\n"
        "## Corner 1 — Evidence\n\nReal content here, well past the threshold for a "
        "populated corner section.\n\n"
        "## Corner 2 — Constraint Relation\n\nReal content here, well past the threshold "
        "for a populated corner section.\n\n"
        "## Corner 3 — Blast Radius\n\nThe jwt claim shape is consumed by control-plane and "
        "cli-tool, both of which must migrate.\n\n"
        "## Corner 4 — Verification\n\nReal content here, well past the threshold for a "
        "populated corner section.\n\n"
        "## Recommendation\n\n- Do X\n",
    )
    _rc, data = _run(path, path.parents[4])
    assert "no_adr_on_cross_repo_change" in data["hard_caps_triggered"]
    assert data["final_score_after_caps"] <= 70.0
