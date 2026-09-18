"""The root `sq` shim, executed — because nothing else looks at it.

Four gates all miss this file. `verify_ecosystem.check_python_syntax` filters on
`.py`; `check_shell_syntax` globs `hooks/*.sh`, `skills/**/*.sh`, `mechanisms/**/*.sh`;
`ruff` in CI is given directories; `shellcheck` in CI reads `git ls-files '*.sh'`. An
extensionless root file matches none of them.

That was a deliberate trade — the short command name against the syntax gate — and this
file is the other half of it. A shim that does not parse fails here.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQ = ROOT / "sq"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SQ), *args], capture_output=True, text=True, timeout=60, cwd=ROOT
    , check=False)


def test_the_shim_exists_and_is_executable() -> None:
    assert SQ.is_file()
    assert SQ.stat().st_mode & 0o111, "sq is not executable; `./sq` would fail"


def test_help_succeeds_and_names_the_verbs() -> None:
    done = _run("--help")
    assert done.returncode == 0, done.stderr
    for verb in ("where", "run"):
        assert verb in done.stdout, f"--help does not mention {verb!r}"


def test_a_bare_invocation_exits_two_not_zero() -> None:
    """Nothing was asked, so nothing was measured — and 2 is the house's word for that.

    argparse with subparsers would have exited 0 here. A command that did nothing and
    reported success is the exact doctrine this CLI was built to uphold.
    """
    done = _run()
    assert done.returncode == 2
    assert done.stdout == "", "usage on a failed invocation belongs on stderr"
    assert "usage" in done.stderr.lower()


def test_an_unknown_verb_names_the_known_ones() -> None:
    """Guessing wrong should cost one call, not two."""
    done = _run("wehre")
    assert done.returncode == 2
    assert "where" in done.stderr


def test_a_real_verb_runs_through_the_shim() -> None:
    done = _run("where", "check_xrefs")
    assert done.returncode == 0, done.stderr
    assert "mechanisms/gates/check_xrefs.py" in done.stdout


def test_every_verb_reports_what_it_did_not_check() -> None:
    """The load-bearing property, asserted end to end rather than on a dataclass."""
    done = _run("where", "check_xrefs", "--json")
    assert done.returncode == 0, done.stderr
    import json

    payload = json.loads(done.stdout)
    assert payload["not_checked"], (
        "--json omitted `not_checked`; a programmatic consumer would get exactly the "
        "false-coverage report this field exists to prevent"
    )
