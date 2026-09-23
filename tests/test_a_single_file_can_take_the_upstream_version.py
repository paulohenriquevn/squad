"""A consumer could ignore a kit fix or reinstall 400 files, and nothing in between.

`install.sh` has two modes and both replace the whole kit. `boundary-check` refuses editing
a kit file inside an install, with a reason that is right for a fix somebody WROTE there:
*a fix written inside an installed kit protects exactly one machine and is erased by the
next install — open an issue on the kit's repository.*

It has no answer for the other case: a file that differs because the KIT moved and this
install did not. Measured 2026-09-23 across four consumers (stepguard, gitsafety, hodor,
talkex — identical distributions): 400 files differ, splitting into diverged 349,
install_ahead 1, stale 10, kit_ahead 40. `--apply-upstream` applies to the last two — 50
files — and refuses the other 350.

THE REFUSAL IS THE DESIGN, and it costs real coverage: 22 of the 349 diverged differ by four
lines or fewer, 83 by ten or fewer, and this refuses every one. *Is this my work or my lag*
is exactly the judgement `check_install_drift` states, in its own output, that it cannot
make, and a small diff is not evidence of the answer. A command that appears to settle it
would be used where it does not.

What it covers is the case with nothing to lose on either side: the install holds no line
the kit lacks, so taking the kit's version deletes nothing.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = _ROOT / "mechanisms" / "distribution" / "install.sh"


def _trees(tmp_path: Path, *, install: str, kit: str,
           rel: str = "mechanisms/cycle/thing.py") -> tuple[Path, Path]:
    consumer, kitroot = tmp_path / "consumer", tmp_path / "kit"
    for root, body in ((consumer / ".claude", install), (kitroot, kit)):
        (root / Path(rel).parent).mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body, encoding="utf-8")
        for tree in ("skills", "rules", "hooks"):
            (root / tree).mkdir(parents=True, exist_ok=True)
    return consumer, kitroot


def _apply(consumer: Path, kit: Path, rel: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(INSTALLER), str(consumer), "--apply-upstream", rel,
         "--from", str(kit)],
        capture_output=True, text=True, check=False)


REL = "mechanisms/cycle/thing.py"


def test_a_file_the_install_only_lags_on_takes_the_kit_version(tmp_path: Path) -> None:
    consumer, kit = _trees(tmp_path, install="a = 1\n", kit="a = 1\nb = 2\n")

    out = _apply(consumer, kit, REL)

    assert out.returncode == 0, out.stdout + out.stderr
    assert (consumer / ".claude" / REL).read_text(encoding="utf-8") == "a = 1\nb = 2\n"


def test_a_diverged_file_is_refused_and_left_alone(tmp_path: Path) -> None:
    """The install holds a line the kit lacks, so nobody here can say whose it is."""
    consumer, kit = _trees(tmp_path, install="a = 1\nmine = True\n", kit="a = 1\ntheirs = True\n")

    out = _apply(consumer, kit, REL)

    assert out.returncode == 1
    assert "DIVERGED" in out.stdout + out.stderr
    assert (consumer / ".claude" / REL).read_text(encoding="utf-8") == "a = 1\nmine = True\n"


def test_an_install_ahead_file_is_refused_too(tmp_path: Path) -> None:
    """The one class whose lines an upgrade DELETES is the one this must not touch."""
    consumer, kit = _trees(tmp_path, install="a = 1\nonly_here = True\n", kit="a = 1\n")

    out = _apply(consumer, kit, REL)

    assert out.returncode == 1
    assert "INSTALL_AHEAD" in out.stdout + out.stderr
    assert "only_here" in (consumer / ".claude" / REL).read_text(encoding="utf-8")


def test_an_identical_file_says_so_and_changes_nothing(tmp_path: Path) -> None:
    """Already current is not an error, and it is not a copy either."""
    consumer, kit = _trees(tmp_path, install="a = 1\n", kit="a = 1\n")

    out = _apply(consumer, kit, REL)

    assert out.returncode == 0
    assert "IDENTICAL" in out.stdout + out.stderr


def test_a_file_the_kit_does_not_ship_is_refused(tmp_path: Path) -> None:
    """There is no upstream version to take, and inventing one would delete the file."""
    consumer, kit = _trees(tmp_path, install="a = 1\n", kit="a = 1\n")
    (kit / REL).unlink()

    out = _apply(consumer, kit, REL)

    assert out.returncode == 2
    assert (consumer / ".claude" / REL).is_file()


def test_a_path_outside_the_install_is_refused(tmp_path: Path) -> None:
    """`../` is how a per-file copy becomes a write anywhere."""
    consumer, kit = _trees(tmp_path, install="a = 1\n", kit="a = 1\nb = 2\n")

    out = _apply(consumer, kit, "../outside.py")

    assert out.returncode == 2
    assert not (tmp_path / "consumer" / "outside.py").exists()


def test_a_project_owned_path_is_refused(tmp_path: Path) -> None:
    """`rules/*.txt` and `agents/` are the project's, and the kit's version of them is a
    template. Overwriting one is what `--merge` exists to avoid."""
    consumer, kit = _trees(tmp_path, install="live = 1\n", kit="template = 1\n",
                           rel="rules/live-target.txt")

    out = _apply(consumer, kit, "rules/live-target.txt")

    assert out.returncode == 2
    assert "live = 1" in (consumer / ".claude" / "rules" / "live-target.txt").read_text()


def test_an_install_whose_claude_is_a_symlink_is_still_writable(tmp_path: Path) -> None:
    """Resolving one side of the containment check and not the other refuses a real layout.

    The guard asks realpath where `<install>/<path>` lands, so a `..` that normalises out of
    the install is caught however it is spelled. Compared against an UNRESOLVED `$ECO`, that
    same resolution refuses every install whose `.claude` is a symlink — the path resolves
    to the link's target, which shares no prefix with the link. Fail-closed on the wrong
    question is still the wrong answer, and the message names a path the operator never wrote.
    """
    real, proj = tmp_path / "real", tmp_path / "proj"
    (real / "mechanisms" / "cycle").mkdir(parents=True)
    (real / "mechanisms" / "cycle" / "thing.py").write_text("a = 1\n", encoding="utf-8")
    proj.mkdir()
    (proj / ".claude").symlink_to(real)
    kit = tmp_path / "kit"
    (kit / "mechanisms" / "cycle").mkdir(parents=True)
    (kit / "mechanisms" / "cycle" / "thing.py").write_text("a = 1\nb = 2\n", encoding="utf-8")

    out = _apply(proj, kit, REL)

    assert out.returncode == 0, out.stdout + out.stderr
    assert (real / REL).read_text(encoding="utf-8") == "a = 1\nb = 2\n"

    # And the containment guard still holds in exactly that layout.
    escape = _apply(proj, kit, "../../etc/passwd")
    assert escape.returncode == 2
    assert "outside the install" in escape.stdout + escape.stderr


def _kit_with_history(tmp_path: Path) -> Path:
    """A kit whose git history holds the revision the consumer is stuck on."""
    kit = tmp_path / "kitrepo"
    (kit / "mechanisms" / "cycle").mkdir(parents=True)
    for tree in ("skills", "rules", "hooks"):
        (kit / tree).mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(kit)], check=True)
    run = lambda *a: subprocess.run(["git", "-C", str(kit), *a], check=True,
                                    capture_output=True, text=True)
    run("config", "user.email", "t@t"); run("config", "user.name", "t")
    old = "# the rule — measured, not assumed · naïve\nalpha\nbeta\n"
    (kit / REL).write_text(old, encoding="utf-8")
    run("add", "-A"); run("commit", "-qm", "v1")
    (kit / REL).write_text("# the rule — measured, not assumed · naïve\nalpha\nBETA-rewritten\ngamma\n",
                           encoding="utf-8")
    run("add", "-A"); run("commit", "-qm", "v2 rewrites and appends")
    return kit


def test_a_stale_file_is_applied_not_refused(tmp_path: Path) -> None:
    """The scan says STALE and this refused it as DIVERGED — same function, two callers.

    `classify_file` promotes DIVERGED to STALE only when given `kit_root` AND `rel`; the
    scan passes both, and this passed neither, so the promotion could not run and the
    tool refused exactly the files the checker had just declared applicable. Reported by
    a consumer that verified MEMBERSHIP of the stale list rather than its count, then
    could not act on it.

    `rel` is also what enables the project-owned guard inside `classify_file`, so that
    call was not consulting ownership either.
    """
    kit = _kit_with_history(tmp_path)
    consumer = tmp_path / "consumer"
    (consumer / ".claude" / Path(REL).parent).mkdir(parents=True)
    for tree in ("skills", "rules", "hooks"):
        (consumer / ".claude" / tree).mkdir(parents=True, exist_ok=True)
    # Byte-identical to v1: proven lag, nothing of the consumer's in it.
    (consumer / ".claude" / REL).write_text("# the rule — measured, not assumed · naïve\nalpha\nbeta\n",
                                            encoding="utf-8")

    out = _apply(consumer, kit, REL)

    assert out.returncode == 0, out.stdout + out.stderr
    assert "stale" in (out.stdout + out.stderr).lower(), out.stdout + out.stderr
    assert (consumer / ".claude" / REL).read_text(encoding="utf-8") == (
        kit / REL).read_text(encoding="utf-8")
