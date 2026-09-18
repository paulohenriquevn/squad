"""The aggregator's `--json` must name the checks that did not run, not count them.

`verify_ecosystem.py` runs 25 checks and is the one gate a consumer points at to ask
"is this install sound". It had no `--json` at all: a programmatic caller got an exit
code and, in prose, `(N not run — each ⊘ above says why)`. The reasons were on screen
and nowhere a parser could reach them, so anything consuming this gate machine-side
saw a pass with no way to learn that sixteen of the checks never executed.

That is the false-coverage report `squad/cli/report.py § not_checked` was written to
prevent — "making it a printed line would have fixed the human channel and left
`--json` saying `{"passed": 1894}`" — committed by the file that aggregates every
other gate in the kit.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "mechanisms" / "gates" / "verify_ecosystem.py"


def _json(root: Path) -> dict:
    done = subprocess.run([sys.executable, str(GATE), "--root", str(root), "--json"],
                          capture_output=True, text=True, timeout=900, check=False)
    assert done.stdout.lstrip().startswith("{"), (
        "stdout is not parseable JSON — the human text raced the payload:\n"
        + done.stdout[:400])
    return json.loads(done.stdout)


def test_a_tree_with_no_gates_says_which_checks_did_not_run(tmp_path: Path) -> None:
    """Sixteen skips, each with its own reason. Not a number."""
    payload = _json(tmp_path)

    assert payload["not_checked"], (
        "every delegating check skipped and `not_checked` was empty — an empty list "
        "there is a claim that nothing was missed, and it must be true")
    assert len(payload["not_checked"]) == payload["detail"]["not_run"], (
        "the prose count and the machine-readable list disagree about how much "
        "of the suite ran")
    assert all(":" in entry for entry in payload["not_checked"]), (
        f"a skip was recorded without its reason: {payload['not_checked']}")


def test_the_human_text_survives_into_the_payload(tmp_path: Path) -> None:
    """Captured, not suppressed. The per-check detail is the whole value of the run."""
    payload = _json(tmp_path)

    assert payload["lines"], "`--json` dropped the human report instead of carrying it"
    assert any("⊘" in line for line in payload["lines"]), (
        "the skip markers did not survive into `lines`")


def test_the_text_run_is_unchanged_by_the_flag_existing(tmp_path: Path) -> None:
    """A reporting flag that alters the verdict is a flag nobody can trust."""
    plain = subprocess.run([sys.executable, str(GATE), "--root", str(tmp_path)],
                           capture_output=True, text=True, timeout=900, check=False)

    assert plain.returncode == _json(tmp_path)["exit_code"], (
        "`--json` and the text run reached different verdicts on the same tree")
    assert not plain.stdout.lstrip().startswith("{"), (
        "the text run emitted JSON:\n" + plain.stdout[:200])
