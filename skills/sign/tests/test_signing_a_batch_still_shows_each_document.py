"""Signing several documents at once must not become signing without reading.

`SKILL.md` argues the position this file holds to: *"A tool that makes signing
frictionless turns a signature into a stamp, which is the failure the machine's own
refusal exists to prevent"*, and *"there is no `--yes` — adding one would remove the
only thing this contributes over `sed`."*

`--all` exists because four points in the chain stop at once — the product documents
are written together and read together — and typing the same command four times is
friction that buys nothing. What it must NOT do is buy speed with the preview.

So the batch keeps both halves of the single-document contract:

  * the default run writes nothing and prints every document's sign-off section
  * `--confirm` is still a second, deliberate act
  * a refusal on one document does not sign it, and does not stop the others

The last one is the case a reader should look at hardest. A batch that aborts on the
first refusal leaves the earlier documents signed and the later ones untouched, with
no record of where it stopped — half-applied, which is worse than either outcome.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "skills" / "sign" / "scripts" / "sign_document.py"

_SIGNABLE = "# {title}\n\n## Sign-off\n\n- [ ] Read and holds\n"


def _project(tmp_path: Path, *names: str) -> Path:
    """A project whose write root holds one signable document per name."""
    product = tmp_path / ".squad" / "wiki" / "product"
    product.mkdir(parents=True)
    for name in names:
        (product / f"{name}.md").write_text(_SIGNABLE.format(title=name), encoding="utf-8")
    return tmp_path


def _run(project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--all", "--as", "paulo",
         "--project", str(project), *extra],
        capture_output=True, text=True, timeout=120, check=False)


def test_the_default_batch_run_writes_nothing(tmp_path: Path) -> None:
    """Same contract as one document: print, and touch the disk only on `--confirm`."""
    project = _project(tmp_path, "vision", "objectives")
    before = {p: p.read_text(encoding="utf-8")
              for p in (project / ".squad" / "wiki" / "product").glob("*.md")}

    done = _run(project)

    assert done.returncode == 0, done.stdout + done.stderr
    for path, text in before.items():
        assert path.read_text(encoding="utf-8") == text, f"{path.name} was modified"


def test_every_document_in_the_batch_is_shown(tmp_path: Path) -> None:
    """The whole reason the flag is allowed to exist."""
    project = _project(tmp_path, "vision", "objectives", "trd")

    done = _run(project)

    for name in ("vision", "objectives", "trd"):
        assert name in done.stdout, (
            f"{name} would have been signed without being shown:\n{done.stdout}")
    assert done.stdout.count("The sign-off section, verbatim:") == 3, (
        "the sign-off sections were summarised away rather than shown:\n" + done.stdout)


def test_the_batch_says_how_many_and_how_to_proceed(tmp_path: Path) -> None:
    """A preview that does not say what `--confirm` would do is a preview of nothing."""
    project = _project(tmp_path, "vision", "objectives")

    done = _run(project)

    assert "2" in done.stdout, "the count is not stated"
    assert "--confirm" in done.stdout, "the second act is not named"


def test_confirm_signs_all_of_them(tmp_path: Path) -> None:
    project = _project(tmp_path, "vision", "objectives")

    done = _run(project, "--confirm", "--despite-authorship",
                "solo project; no second reviewer exists")

    assert done.returncode == 0, done.stdout + done.stderr
    for path in (project / ".squad" / "wiki" / "product").glob("*.md"):
        assert "- [x]" in path.read_text(encoding="utf-8"), f"{path.name} was not signed"


def test_a_refusal_on_one_does_not_stop_the_others(tmp_path: Path) -> None:
    """Half-applied is worse than either outcome, so the batch carries on and reports.

    `already_signed` is the refusal used here because it is the one a batch meets in
    ordinary use: sign three, add a fourth, run again.
    """
    project = _project(tmp_path, "vision", "objectives")
    signed = project / ".squad" / "wiki" / "product" / "vision.md"
    subprocess.run([sys.executable, str(_SCRIPT), str(signed), "--as", "paulo",
                    "--confirm", "--despite-authorship", "solo project; no second reviewer"],
                   capture_output=True, text=True, timeout=120, check=False)

    done = _run(project, "--confirm", "--despite-authorship",
                "solo project; no second reviewer exists")

    other = project / ".squad" / "wiki" / "product" / "objectives.md"
    assert "- [x]" in other.read_text(encoding="utf-8"), (
        "a refusal on one document stopped the batch:\n" + done.stdout + done.stderr)


def test_nothing_waiting_is_not_an_error(tmp_path: Path) -> None:
    """An empty batch says nothing is waiting — which is not "everything is signed",
    the distinction `--list` already makes."""
    project = tmp_path
    (project / ".squad" / "wiki" / "product").mkdir(parents=True)

    done = _run(project)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "nothing is waiting" in (done.stdout + done.stderr).lower()


def test_all_and_a_target_together_are_refused(tmp_path: Path) -> None:
    """Two different intentions in one command. Guessing which one wins is how a
    tool signs something nobody asked it to."""
    project = _project(tmp_path, "vision")
    one = project / ".squad" / "wiki" / "product" / "vision.md"

    done = subprocess.run(
        [sys.executable, str(_SCRIPT), str(one), "--all", "--as", "paulo",
         "--project", str(project)],
        capture_output=True, text=True, timeout=120, check=False)

    assert done.returncode != 0, "the tool picked one of two intentions silently"
    assert "- [x]" not in one.read_text(encoding="utf-8"), "it signed anyway"
