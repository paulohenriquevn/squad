"""A rule the kit withdrew must reach the consumer holding it, as a skill does.

`withdrawn.txt` listed skills only. `install.sh` preserves any `rules/*.md` the source kit
does not ship as the project's own, so a retired rule stayed on disk, was announced as
`kept (yours)` on every `--force`, and — unlike a stale skill — kept LOADING into every
session. Measured on a consumer 2026-09-23: `rules/cycle-auto-plan.md` ("Auto-merge is
forbidden") in the context beside the current `cycle-release.md` ("the system merges a PR
whose whole chain passed"), two contradictory contracts both presented as current.

The same two properties hold as for skills: a withdrawal is reported by name and removed
only on `--remove-withdrawn`, and a rule the project wrote is never called one.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = _ROOT / "mechanisms" / "distribution" / "install.sh"
WITHDRAWN = "rules/cycle-auto-plan.md"   # declared in withdrawn.txt
PROJECTS_OWN = "rules/our-own-rule.md"   # never shipped by the kit


def _consumer(tmp_path: Path) -> Path:
    """An install holding one withdrawn rule and one the project wrote."""
    target = tmp_path / "consumer"
    eco = target / ".claude"
    for tree in ("skills", "rules", "hooks"):
        (eco / tree).mkdir(parents=True, exist_ok=True)
    (eco / WITHDRAWN).write_text("# Auto-merge is forbidden\n", encoding="utf-8")
    (eco / PROJECTS_OWN).write_text("# ours\n", encoding="utf-8")
    return target


def _run(target: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(INSTALLER), str(target), *flags],
                          capture_output=True, text=True, check=False)


def test_a_withdrawn_rule_is_named_in_the_output(tmp_path: Path) -> None:
    target = _consumer(tmp_path)

    out = _run(target, "--merge")

    combined = out.stdout + out.stderr
    withdrawn_section = combined.split("WITHDRAWN by the kit", 1)[-1]
    assert "WITHDRAWN by the kit" in combined, combined[-3000:]
    assert WITHDRAWN in withdrawn_section.split("==>", 1)[0], combined[-3000:]


def test_reporting_does_not_delete_the_rule(tmp_path: Path) -> None:
    target = _consumer(tmp_path)

    _run(target, "--merge")

    assert (target / ".claude" / WITHDRAWN).exists()


def test_remove_withdrawn_deletes_only_the_declared_rule(tmp_path: Path) -> None:
    target = _consumer(tmp_path)

    out = _run(target, "--remove-withdrawn")

    assert out.returncode == 0, (out.stdout + out.stderr)[-3000:]
    assert not (target / ".claude" / WITHDRAWN).exists(), "declared rule survived"
    assert (target / ".claude" / PROJECTS_OWN).exists(), (
        "a rule the kit never shipped was deleted — absence was treated as a withdrawal")


def test_a_force_install_does_not_call_a_withdrawn_rule_the_projects(tmp_path: Path) -> None:
    """`--force` preserves what the kit does not ship and prints `kept (yours)` for it.
    For a declared withdrawal that label is false — the file is the kit's — and it was
    the only line the operator saw about it."""
    target = _consumer(tmp_path)

    out = _run(target, "--force")

    # Not asserting the exit code: this is a label test, and the post-install validation
    # of a bare tmp tree fails on things it does not cover — the stale rule itself among
    # them (`check_xrefs` counts it as a cycle rule), which is why it gets reported.
    combined = out.stdout + out.stderr
    assert f"kept (yours): {WITHDRAWN}" not in combined, combined[-3000:]
    assert f"kept (yours): {PROJECTS_OWN}" in combined, combined[-3000:]
