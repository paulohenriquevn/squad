"""`test_clean_install.py` covers installing. Nothing covered UPGRADING, and that is where
the expensive defects of 2026-09-23 lived.

Six defects were filed that day and five were reported by a consumer running the kit against
a real install, not by the 31 suites. Every one of the five lived on the upgrade path:

  #171  a withdrawn file reached nobody, and a reinstall restored it
  #173  a blob size in BYTES sliced a string of CHARACTERS, so 350 recoverable files
        reported DIVERGED and the upgrade path refused all of them
  -     `--apply-upstream` called `classify_file` with two of its four arguments, so the
        STALE promotion could never run and it refused exactly what the scan had just
        declared applicable
  -     `install.sh` accepted a `.claude` as its target and built a nested install, after
        which every flag acted on the wrong tree

None of them is reachable from a fresh install, because a fresh install has no lag. This
materialises an OLDER revision of the kit, installs THAT into a consumer, and then asks the
current kit about it — the only shape in which lag exists at all.

It is deliberately an integration test with a real `git worktree` and a real install. A
fixture that fabricated "an old install" by editing files would test the fabrication: the
byte/character defect only appears against git's own `cat-file --batch` output, and the
2-argument call only appears when a file genuinely has history.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = _ROOT / "mechanisms" / "distribution" / "install.sh"
DRIFT = _ROOT / "mechanisms" / "gates" / "check_install_drift.py"

#: How far back to stand. Small enough to be fast, large enough that prose files differ —
#: and computed rather than pinned, because a pinned sha rots into a citation nothing
#: resolves, which is a defect class this kit records.
_DEPTH = 12


def _git(*args: str, cwd: Path = _ROOT) -> str:
    out = subprocess.run(["git", "-C", str(cwd), *args],
                         capture_output=True, text=True, check=False)
    return out.stdout.strip()


@pytest.fixture(scope="module")
def old_kit(tmp_path_factory) -> Path:
    """An older revision of this kit, materialised as a real checkout."""
    base = _git("rev-parse", f"HEAD~{_DEPTH}")
    if not base:
        pytest.skip(f"history is shallower than {_DEPTH} commits")
    where = tmp_path_factory.mktemp("old-kit") / "kit"
    added = subprocess.run(
        ["git", "-C", str(_ROOT), "worktree", "add", "--detach", str(where), base],
        capture_output=True, text=True, check=False)
    if added.returncode != 0:
        pytest.skip(f"could not create a worktree at {base[:9]}: {added.stderr.strip()[:200]}")
    yield where
    subprocess.run(["git", "-C", str(_ROOT), "worktree", "remove", "--force", str(where)],
                   capture_output=True, text=True, check=False)


@pytest.fixture(scope="module")
def lagging_consumer(old_kit: Path, tmp_path_factory) -> Path:
    """A project carrying the OLD kit — the only state in which lag exists."""
    project = tmp_path_factory.mktemp("consumer") / "project"
    project.mkdir(parents=True)
    out = subprocess.run(["bash", str(old_kit / "mechanisms" / "distribution" / "install.sh"),
                          str(project)], capture_output=True, text=True, check=False)
    if not (project / ".claude").is_dir():
        pytest.skip(f"the old installer did not produce an install: {out.stderr[-400:]}")
    return project


def _drift(consumer: Path) -> dict[str, int]:
    out = subprocess.run([sys.executable, str(DRIFT), "--install", str(consumer / ".claude"),
                          "--kit", str(_ROOT)], capture_output=True, text=True, check=False)
    counts: dict[str, int] = {}
    for line in out.stdout.splitlines():
        for name in ("diverged", "install_ahead", "stale", "kit_ahead", "identical"):
            if line.startswith(f"{name}:"):
                counts[name] = int(line.split(":")[1].split()[0])
    return counts


def test_the_consumer_actually_lags(lagging_consumer: Path) -> None:
    """The premise. Without difference every assertion below is vacuous."""
    counts = _drift(lagging_consumer)
    moved = sum(counts.get(k, 0) for k in ("diverged", "stale", "kit_ahead", "install_ahead"))
    assert moved > 0, (
        f"{_DEPTH} commits back produced no differing file; this test has no subject. "
        f"counts={counts}")


def test_a_lagging_file_is_classified_as_lag_and_not_as_divergence(lagging_consumer: Path) -> None:
    """#173. The consumer wrote nothing, so nothing here can be its work.

    A body the history reader never produced cannot match, and the file then reports
    DIVERGED — which the upgrade path refuses by design. The whole 350-file refusal came
    from that, and a fresh install cannot show it.
    """
    counts = _drift(lagging_consumer)
    assert counts.get("diverged", 0) == 0, (
        f"a consumer that only lags reported {counts['diverged']} DIVERGED file(s). Either it "
        f"wrote something (it did not) or the history reader is losing revisions. counts={counts}")


def test_the_upgrade_path_applies_what_the_scan_calls_applicable(lagging_consumer: Path) -> None:
    """The 2-argument call. The scan said `stale`; `--apply-upstream` said DIVERGED."""
    counts = _drift(lagging_consumer)
    applicable = counts.get("stale", 0) + counts.get("kit_ahead", 0)
    if applicable == 0:
        pytest.skip("nothing applicable at this depth")

    out = subprocess.run([sys.executable, str(DRIFT), "--install",
                          str(lagging_consumer / ".claude"), "--kit", str(_ROOT)],
                         capture_output=True, text=True, check=False)
    rels: list[str] = []
    grabbing = False
    for line in out.stdout.splitlines():
        if line.startswith(("stale:", "kit_ahead:")):
            grabbing = True
            continue
        if grabbing:
            if line.startswith("    "):
                rels.append(line.strip())
            else:
                grabbing = False
    rels = [r for r in rels if not r.startswith(("agents/", "records/", "settings.json"))]
    assert rels, "the scan named no applicable path; this test lost its subject"

    target = rels[0]
    applied = subprocess.run(["bash", str(INSTALLER), str(lagging_consumer),
                              "--apply-upstream", target], capture_output=True, text=True,
                             check=False)
    combined = applied.stdout + applied.stderr
    assert applied.returncode == 0, (
        f"the scan calls {target} applicable and the upgrade path refused it:\n{combined}")
    assert (lagging_consumer / ".claude" / target).read_bytes() == (_ROOT / target).read_bytes()


def test_the_installer_records_where_it_came_from(lagging_consumer: Path) -> None:
    """Provenance is what makes lag provable rather than inferred; it must be written."""
    manifest = (lagging_consumer / ".claude" / ".kit-manifest.txt").read_text(encoding="utf-8")
    line = next((row for row in manifest.splitlines() if "kit-commit" in row), "")
    assert line, "the manifest records no kit-commit; a consumer cannot prove what it holds"
    assert "unknown" not in line, line


def test_a_withdrawal_declared_by_the_kit_is_named_to_the_consumer(lagging_consumer: Path) -> None:
    """#171. A withdrawal is invisible on disk; only the declared list can surface it."""
    listing = _ROOT / "mechanisms" / "distribution" / "withdrawn.txt"
    declared = [row.split("|")[0].strip() for row in listing.read_text(encoding="utf-8").splitlines()
                if row.strip() and not row.startswith("#") and "|" in row]
    present = [d for d in declared if (lagging_consumer / ".claude" / d).exists()]
    if not present:
        pytest.skip("this older revision shipped none of the declared withdrawals")

    out = subprocess.run(["bash", str(INSTALLER), str(lagging_consumer), "--merge"],
                         capture_output=True, text=True, check=False)
    combined = out.stdout + out.stderr
    for rel in present:
        assert rel in combined, f"{rel} is declared withdrawn, is installed, and was not named"
        assert (lagging_consumer / ".claude" / rel).exists(), (
            f"{rel} was deleted by a --merge; removal must be opt-in")
