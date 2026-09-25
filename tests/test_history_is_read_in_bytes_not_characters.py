"""`git cat-file --batch` declares each blob's size in BYTES. Slicing a decoded string
by that number counts CHARACTERS, and every non-ASCII byte desynchronises the parser.

`_blobs_from_batch` ran the batch with `text=True` and advanced by `size` over the decoded
string. This kit's prose is full of em-dashes and accented words, so the very first blob
containing one left the cursor short by the difference; from there every header read as
payload and every remaining revision was dropped.

Measured 2026-09-23 on `hooks/validate-command.py`: 59104 bytes against 58717 characters —
387 lost per revision from 197 non-ASCII characters. `git rev-list --all` names 14 commits
for that path and `_historical_contents` returned 7 contents, none of them the one the
install actually holds. Confirmed on a real install whose `.kit-manifest.txt` records a
clean, resolving `kit-commit`: the installed file is byte-identical to that commit's blob,
and that blob was absent from the history set.

The consequence ran all the way up. `classify_file` downgrades to STALE when the install's
body appears in history, so a body the parser never produced could not match — and the file
was reported DIVERGED, which `--apply-upstream` refuses. 350 of 350 diverged files in one
consumer, every one of them merely older, all unreachable because a size in bytes was spent
on a string of characters.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mechanisms" / "gates"))


def _kit_with_accents(tmp_path: Path) -> tuple[Path, str]:
    """Two revisions of a file whose prose carries the characters this kit is written in."""
    kit = tmp_path / "kit"
    (kit / "rules").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(kit)], check=True)
    def run(*a):
        return subprocess.run(["git", "-C", str(kit), *a], check=True,
                              capture_output=True, text=True)
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")

    old = "# the rule — measured, not assumed\nalpha\nbeta\n" + ("# façade — naïve · Größe\n" * 40)
    (kit / "rules" / "r.md").write_text(old, encoding="utf-8")
    run("add", "-A")
    run("commit", "-qm", "v1")
    (kit / "rules" / "r.md").write_text(old + "gamma-new\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-qm", "v2 appends")
    (kit / "rules" / "r.md").write_text(old.replace("beta", "beta-rewritten") + "gamma-new\n",
                                        encoding="utf-8")
    run("add", "-A")
    run("commit", "-qm", "v3 rewrites")
    return kit, old


def test_every_revision_is_recovered_from_the_batch(tmp_path: Path) -> None:
    import importlib

    import check_install_drift
    importlib.reload(check_install_drift)
    kit, _old = _kit_with_accents(tmp_path)

    revisions = subprocess.run(["git", "-C", str(kit), "rev-list", "--all", "--", "rules/r.md"],
                               capture_output=True, text=True, check=False).stdout.split()
    history = check_install_drift._historical_contents(kit, "rules/r.md")

    assert history is not None
    assert len(history) == len(revisions), (
        f"{len(revisions)} revisions, {len(history)} contents recovered — the parser lost "
        f"{len(revisions) - len(history)} to a byte size spent on characters")


def test_an_older_copy_with_accents_is_stale_not_diverged(tmp_path: Path) -> None:
    """The verdict the parser bug turned into DIVERGED, which --apply-upstream refuses."""
    import importlib

    import check_install_drift
    importlib.reload(check_install_drift)
    kit, old = _kit_with_accents(tmp_path)
    eco = tmp_path / "consumer" / ".claude"
    (eco / "rules").mkdir(parents=True)
    (eco / "rules" / "r.md").write_text(old, encoding="utf-8")

    verdict = check_install_drift.classify_file(
        eco / "rules" / "r.md", kit / "rules" / "r.md", kit, "rules/r.md")

    assert verdict is check_install_drift.Drift.STALE, verdict
