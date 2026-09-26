r"""The kit's own SOPs are still swept after they left the write root.

`check_sop_structure` sweeps two places: the OKF bundle, which holds procedures ABOUT
the kit — installing it into a consumer, propagating a delta, porting a fix — and each
skill's `SOP.md`, which holds the procedure for OPERATING that skill.

When the bundle moved from `.squad/wiki/` to `docs/wiki/` on 2026-09-21, the first of
those two silently emptied: `resolve_knowledge_dir` answers from the write root, the
write root no longer holds authored documents, and the gate went on reporting a clean
sweep of the remainder. Measured immediately after the move: `read 39 SOPs`, down from
43, with nothing in the output saying four had left.

That is the exact shape this kit names more often than any other — a sweep that covers
less and reports the same — and the move caused it rather than finding it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "mechanisms" / "gates"))
sys.path.insert(0, str(REPO / "mechanisms" / "conventions"))
sys.path.insert(0, str(REPO))

from check_sop_structure import check_sop_structure  # noqa: E402

BUNDLE_SOPS = REPO / "docs" / "wiki" / "sops"


def test_the_bundle_sops_exist_where_the_product_is() -> None:
    """The premise. Without it the rest of this file proves nothing."""
    assert BUNDLE_SOPS.is_dir()
    assert len([p for p in BUNDLE_SOPS.glob("*.md") if p.name != "index.md"]) >= 4


def test_every_authored_sop_is_swept() -> None:
    """Each one by name, so a sweep that drops one cannot pass by counting."""
    report = check_sop_structure(REPO)

    assert report.sops_read >= 43, (
        f"read {report.sops_read} SOPs; the four in docs/wiki/sops/ are not being swept"
    )


def test_the_gate_says_how_many_it_read() -> None:
    """A sweep that covers less must not read identically to one that covers more."""
    done = subprocess.run(
        [sys.executable, str(REPO / "mechanisms" / "gates" / "check_sop_structure.py")],
        cwd=REPO, capture_output=True, text=True,
        check=False,
    )

    assert "SOP" in done.stdout, done.stdout + done.stderr
    assert done.returncode == 0, done.stdout + done.stderr


def test_a_project_with_no_authored_bundle_still_sweeps_its_skills(tmp_path: Path) -> None:
    """`docs/wiki/` is where THIS kit keeps its authored documents. A project without
    one is not an error, and its skill SOPs must still be read."""
    skill = tmp_path / "skills" / "thing"
    skill.mkdir(parents=True)
    (skill / "SOP.md").write_text(
        "---\nname: thing\nlast_reviewed: 2026-09-01\nreview_interval_days: 180\n---\n\n"
        "# SOP: thing\n\n## Preconditions\n\n- none\n\n## Steps\n\n1. do it\n\n"
        "## Verdicts\n\n- DONE\n",
        encoding="utf-8")

    report = check_sop_structure(tmp_path)

    assert report.sops_read == 1
