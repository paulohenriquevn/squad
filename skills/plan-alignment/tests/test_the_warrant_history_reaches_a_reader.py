"""Four fields were computed for a reader and shown to nobody.

`withdrawal_reason`, `sign_off_restored`, `restoration_reason` and
`unmarked_withdrawal_prose` are built by `score_alignment` and appeared on NEITHER
output path — not in the `--json` payload, not in the text report. The source states
what each is for: `unmarked_withdrawal_prose` is "quoted so the reviewer knows exactly
which line to mark"; `sign_off_restored` is "Reported so a reader can see the warrant
was taken back and given again". No reader could see either.

A withdrawal nobody can see reads as a sign-off nobody gave, which is the direction
that matters: the brief still scores as warranted.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "skills" / "plan-alignment" / "scripts" / "score_alignment.py"

_BRIEF = """# A brief

## Reviewer sign-off

- [x] Judged by: someone  <!-- signed-by: human/paulo -->

<!-- sign-off: WITHDRAWN: the flows changed after I signed -->
"""


def _run(tmp_path: Path, body: str, *extra: str) -> subprocess.CompletedProcess[str]:
    brief = tmp_path / "a-brief.md"
    brief.write_text(body, encoding="utf-8")
    return subprocess.run([sys.executable, str(_SCRIPT), str(brief), *extra],
                          capture_output=True, text=True, timeout=180, check=False)


def test_the_json_carries_the_withdrawal_and_its_reason(tmp_path: Path) -> None:
    payload = json.loads(_run(tmp_path, _BRIEF, "--json").stdout)

    assert payload["sign_off_withdrawn"] is True
    assert "the flows changed after I signed" in payload["withdrawal_reason"]


def test_the_text_report_says_the_sign_off_was_withdrawn(tmp_path: Path) -> None:
    out = _run(tmp_path, _BRIEF).stdout

    assert "SIGN-OFF WITHDRAWN" in out, out[-500:]
    assert "the flows changed after I signed" in out


def test_a_restoration_is_reported_as_a_restoration(tmp_path: Path) -> None:
    body = _BRIEF + "\n<!-- sign-off: RESTORED: the flows are back -->\n"

    payload = json.loads(_run(tmp_path, body, "--json").stdout)

    assert payload["sign_off_restored"] is True
    assert payload["sign_off_withdrawn"] is False, "restored is not still withdrawn"
    assert "the flows are back" in payload["restoration_reason"]


def test_the_json_carries_every_warrant_field(tmp_path: Path) -> None:
    payload = json.loads(_run(tmp_path, "# A brief\n", "--json").stdout)

    for field in ("sign_off_withdrawn", "withdrawal_reason", "sign_off_restored",
                  "restoration_reason", "unmarked_withdrawal_prose"):
        assert field in payload, f"{field} is computed and published nowhere"
