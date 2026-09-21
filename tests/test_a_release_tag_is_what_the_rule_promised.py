r"""The tag-cut gate must be one a correct release can pass.

`cycle-release.md` declared, in its phase-contract table, that the tag-cut gate is
`git tag --verify` resolving. The same rule's Step 7 cuts the tag with `git tag -a` —
annotated, not signed. Those two cannot both hold. Measured:

    $ git tag -a v1.0.0 -m "release" && git tag --verify v1.0.0
    error: no signature found
    exit=1

`--verify` checks a GPG SIGNATURE. Every tag this kit cuts correctly would have failed
the gate its own rule declared, and no release ever noticed because the gate was never
mechanised — the table promised a check that nothing ran.

Alongside it sat a second declared-but-absent gate: *"Tag must be annotated (`git tag -a`)
and pushed only after merge to `main`"*, carried as debt since 2026-09-01 with the note
that "nothing inspects the tag object's type or the branch it was cut from". Both are one
question about a finished tag, and `check_tag_integrity.py` is where it is now asked.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "mechanisms" / "gates" / "check_tag_integrity.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.email=a@b", "-c", "user.name=a", *args],
        cwd=repo, capture_output=True, text=True, check=True,
    )


def _repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main", ".")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "first")
    return tmp_path


def _check(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), "--root", str(repo), *args],
        capture_output=True, text=True,
    )


def test_an_annotated_tag_on_the_trunk_passes(tmp_path: Path) -> None:
    """The tag the rule tells you to cut must pass the gate the rule declares."""
    repo = _repo(tmp_path)
    _git(repo, "tag", "-a", "v1.0.0", "-m", "Release v1.0.0")

    result = _check(repo, "--tag", "v1.0.0", "--trunk", "main")

    assert result.returncode == 0, result.stdout + result.stderr


def test_a_lightweight_tag_is_refused(tmp_path: Path) -> None:
    """`git tag v1.0.0` carries no tagger, no date and no message."""
    repo = _repo(tmp_path)
    _git(repo, "tag", "v1.0.0")

    result = _check(repo, "--tag", "v1.0.0", "--trunk", "main")

    assert result.returncode == 1, result.stdout
    assert "annotated" in (result.stdout + result.stderr)


def test_a_tag_cut_off_the_trunk_is_refused(tmp_path: Path) -> None:
    """A tag on a commit that never merged marks a release nobody can check out of main."""
    repo = _repo(tmp_path)
    _git(repo, "switch", "-q", "-c", "workspace")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "unmerged")
    _git(repo, "tag", "-a", "v1.0.0", "-m", "Release v1.0.0")

    result = _check(repo, "--tag", "v1.0.0", "--trunk", "main")

    assert result.returncode == 1, result.stdout
    assert "main" in (result.stdout + result.stderr)


def test_a_missing_tag_cannot_be_measured_and_says_so(tmp_path: Path) -> None:
    """An absent tag is not a passing tag. `2` is the kit's could-not-sweep code."""
    repo = _repo(tmp_path)

    result = _check(repo, "--tag", "v9.9.9", "--trunk", "main")

    assert result.returncode == 2, result.stdout


def test_the_gate_does_not_demand_a_signature(tmp_path: Path) -> None:
    """The defect, pinned: an unsigned annotated tag is CORRECT here.

    Restoring `git tag --verify` as the check would make every tag this kit cuts fail.
    """
    repo = _repo(tmp_path)
    _git(repo, "tag", "-a", "v1.0.0", "-m", "Release v1.0.0")
    verify = subprocess.run(["git", "tag", "--verify", "v1.0.0"],
                            cwd=repo, capture_output=True, text=True)

    assert verify.returncode != 0, "premise: an unsigned annotated tag fails --verify"
    assert _check(repo, "--tag", "v1.0.0", "--trunk", "main").returncode == 0, (
        "...and the gate must pass it anyway"
    )


def test_the_rule_no_longer_declares_an_unsatisfiable_gate() -> None:
    """The tag-cut ROW is what a reader obeys; the prose around it is history.

    The assertion is scoped to the phase-contract row rather than to the whole file on
    purpose. The rule must still be able to SAY `git tag --verify` — the paragraph that
    records why the clause was replaced would be unwritable otherwise, and a correction
    nobody can explain is one somebody undoes.
    """
    rule = (REPO / "rules" / "cycle-release.md").read_text(encoding="utf-8")
    rows = [line for line in rule.splitlines() if line.startswith("| tag-cut")]

    assert rows, "the tag-cut phase-contract row is gone"
    assert "--verify" not in rows[0], (
        f"`--verify` demands a GPG signature and this cycle cuts unsigned annotated "
        f"tags, so the row would refuse every correct release: {rows[0]}"
    )
    assert "check_tag_integrity.py" in rows[0], (
        "the tag-cut gate must name the mechanism that computes it"
    )
