"""Two fleets on one machine wrote their decisions into one file.

`/tmp/squad-lead.jsonl` was the default in three places — `fleet_idle.py`,
`start_fleet.sh`, `fleet_status.sh` — so every reader of a lead log (the board's lead
panel, the idle report, the status script) saw two fleets interleaved and could not tell
whose decision was whose.

Not hypothetical. Measured on this machine 2026-09-16: two sessions writing one
`/tmp/<short-name>.log` from their push wrappers, and one read the OTHER's push output —
different repository, different SHAs, same filename — and reported it as its own for a
turn. What caught it was checking the claim against the repository rather than against
the log. Confirm against the thing, never against the report of the thing.

A lead log belongs to a project the way records do, so it lives beside them and
`squad.paths` owns the path. `LOG=` still overrides for anyone who wants it elsewhere.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from squad.paths import lead_log_path  # noqa: E402 — post-bootstrap import

_FLEET = _ROOT / "mechanisms" / "fleet"


def test_two_projects_get_two_logs(tmp_path: Path) -> None:
    one, two = tmp_path / "alpha", tmp_path / "beta"
    assert lead_log_path(one) != lead_log_path(two), \
        "two fleets on one machine would write into the same file"


def test_the_log_sits_beside_the_project_records(tmp_path: Path) -> None:
    assert lead_log_path(tmp_path).parent == tmp_path / ".squad"


def test_no_reader_spells_the_old_shared_default() -> None:
    """Three copies is how they came to disagree; a fourth is how it returns."""
    offenders = []
    for path in list(_FLEET.glob("*.py")) + list(_FLEET.glob("*.sh")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "/tmp/squad-lead" in line and not line.lstrip().startswith("#"):
                offenders.append(f"{path.name}:{i}")
    assert not offenders, f"a shared /tmp default came back: {offenders}"


def test_the_derivation_runs(tmp_path: Path) -> None:
    """The shells derive the path by calling the owner. A snippet that does not run is a
    default that silently becomes empty — worse than the literal it replaced."""
    script = (_FLEET / "start_fleet.sh").read_text(encoding="utf-8")
    match = re.search(r'LOG="\$\{LOG:-\$\((python3 .*?)\)\}"', script, re.S)
    assert match, "the derivation is not where the reader expects it"
    result = subprocess.run(["bash", "-c", f'_here="{_FLEET}"; PROJECT="{tmp_path}"; '
                                           f'echo "${{LOG:-$({match.group(1)})}}"'],
                            capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(lead_log_path(tmp_path)), result.stdout
