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


def _mirror_repo(real_root: Path, tmp_path: Path) -> Path:
    """A stand-in repository the test may write to, sharing the real one's tree.

    Every top-level entry is symlinked, so a repo-relative pointer in the artifact still
    resolves to the real file — which is why this fixture needed the real root in the
    first place. `.squad` is the exception: it is copied shallowly so the routing table
    and the records this test writes land on the copy.

    ## Why this replaced writing into the checkout

    The fixture used to write `rules/domain-routing.txt` in the repository itself
    whenever the shipped table held no data rows, which is how the kit ships it, and
    restore it after `yield`. That restore was the entire safety mechanism and teardown
    is not guaranteed: kill the run — a CI timeout, Ctrl-C, an interrupted slice — and
    the checkout is left holding two lines of test fixture in place of a 29-line rule
    file. Observed on 2026-09-11, and found only because an unrelated `git status`
    showed the file modified (#87).

    A test that can corrupt its own repository when killed should not be able to,
    however careful its teardown is.
    """
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    for entry in real_root.iterdir():
        if entry.name in (".squad", ".git"):
            continue
        (mirror / entry.name).symlink_to(entry)
    # A real `.git` would make the mirror look like the same repository to anything that
    # walks up looking for one; an empty marker directory is enough for root detection.
    (mirror / ".git").mkdir()
    real_data = real_root / ".squad"
    if real_data.is_dir():
        for entry in real_data.iterdir():
            target = mirror / ".squad" / entry.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(entry)
    else:
        (mirror / ".squad").mkdir()
    return mirror


@pytest.fixture
def staged(project_root: Path, tmp_path: Path):
    """Write an opportunity inside a mirror of the repo, never inside the repo.

    Pointer resolution walks up from the artifact, so an artifact parked in a bare
    temporary directory would resolve every repo-relative pointer as fabricated. The
    mirror keeps that property — the tree is the real one through symlinks — while
    keeping every write this test makes off the checkout.
    """
    root = _mirror_repo(project_root, tmp_path)

    # The routing table: this repository ships it with no data rows on purpose
    # (`agents/README.md` records what shipping a populated one cost an adopter), and
    # cross-repo detection needs one. On the mirror it is simply written — there is
    # nothing to preserve and nothing to restore.
    table = root / ".squad" / "domain-routing.txt"
    if table.is_symlink() or table.exists():
        table.unlink()
    table.write_text(
        "contracts | contracts | agents/contracts.md\n"
        "platform  | control-plane, cli-tool | agents/platform.md\n",
        encoding="utf-8",
    )

    def _write(name: str, content: str) -> Path:
        directory = write_records_dir(root, "discoveries") / "opportunities"
        # The mirrored `.squad/records` is a symlink to the real one; replace it with a
        # real directory before writing, or these artifacts land in the checkout.
        for part in (directory, *directory.parents):
            if part.is_symlink():
                part.unlink()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(content, encoding="utf-8")
        return path

    yield _write


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
    good_opportunity: Path, project_root: Path, records_root: Path, tmp_path: Path
) -> None:
    """The other side: convened, approved, and the structural verdict stands."""
    slug = good_opportunity.stem.replace("-opportunity", "")
    # `records_root`, not the kit root: the panel MACHINERY is the kit's and the panel
    # RECORD is the project's. The same directory when developing, two directories when
    # installed — and writing to the kit's side reports `no_record` forever.
    base = write_records_dir(records_root)
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
                # The approving majority must SPAN two families. Two Claudes approving
                # over the orthogonal seat's objection is the correlated approval the
                # seat exists to prevent, and it now returns the document.
                {"reviewer": "leonardo-researcher", "model": "claude-sonnet-5",
                 "verdict": "return", "reason": why},
                {"reviewer": "judge-codex:discover-judge", "model": "gpt-5-codex",
                 "verdict": "approve", "reason": why},
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


def test_the_fixture_never_writes_into_the_checkout(project_root: Path, tmp_path: Path):
    """The guard for #87, asserted rather than trusted to a teardown.

    The old fixture wrote `rules/domain-routing.txt` in the repository and restored it
    after `yield`. Teardown does not run when a process is killed, so an interrupted
    slice left the checkout holding two lines of test fixture in place of a 29-line rule
    file — found by an unrelated `git status`, days later.

    This asserts the property directly: build the mirror, write through it, and the real
    file is byte-identical afterwards. A test that cannot corrupt its repository does
    not need a teardown to be careful.
    """
    real_table = project_root / "rules" / "domain-routing.txt"
    before = real_table.read_bytes() if real_table.is_file() else None

    root = _mirror_repo(project_root, tmp_path)
    mirror_table = root / ".squad" / "domain-routing.txt"
    if mirror_table.is_symlink() or mirror_table.exists():
        mirror_table.unlink()
    mirror_table.write_text("contracts | contracts | agents/contracts.md\n",
                            encoding="utf-8")

    assert mirror_table.read_text(encoding="utf-8").startswith("contracts")
    after = real_table.read_bytes() if real_table.is_file() else None
    assert after == before, "the fixture wrote into the checkout"


def test_the_mirror_keeps_repo_relative_pointers_resolvable(project_root: Path,
                                                            tmp_path: Path):
    """The property the real root was there for in the first place.

    Pointer resolution walks up from the artifact. If the mirror did not carry the real
    tree, every repo-relative pointer in an opportunity would score as fabricated and
    these tests would pass for the wrong reason.
    """
    root = _mirror_repo(project_root, tmp_path)
    for cited in ("rules/cycle-discover.md",
                  "skills/discover-confidence/scripts/check_evidence_pointers.py"):
        assert (root / cited).is_file(), f"{cited} does not resolve through the mirror"
