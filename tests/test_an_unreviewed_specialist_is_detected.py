"""Check 9 keyed on a marker no shipped writer emits.

`UNREVIEWED_MARKER` was `<!-- TO BE FILLED IN: only a human knows this -->`, kept "in
sync with detect_domains.UNREVIEWED_MARKER" — and `detect_domains.render_specialist`,
the only producer of that string, was a second template for `agents/<domain>.md`
reachable from nothing but its own tests. The LIVE renderer is
`scaffold_specialists.render`, which marks the three judgement sections with a trailing
`— OPEN`.

So the gate that exists to WARN "this specialist is a skeleton nobody reviewed" could
not fire on any specialist the kit actually writes: every derived one passed by not
being detectable. A gate keyed on a string nothing produces is a gate that reports
clean over the case it was written for.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "skills" / "backlog-init" / "scripts"))

from scaffold_specialists import render  # noqa: E402 — post-bootstrap import


def _kit(tmp_path: Path) -> Path:
    for tree in ("skills", "rules", "hooks", "agents"):
        (tmp_path / tree).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _findings(root: Path) -> list[dict]:
    import json
    done = subprocess.run(
        [sys.executable, str(_ROOT / "mechanisms" / "gates" / "check_xrefs.py"),
         "--ecosystem-dir", str(root), "--json"],
        capture_output=True, text=True, timeout=180, check=False)
    payload = json.loads(done.stdout[done.stdout.index("{"):])
    return [f for f in payload["findings"] if f["check"] == "specialist_unreviewed"]


def test_a_scaffolded_specialist_is_reported_as_unreviewed(tmp_path: Path) -> None:
    root = _kit(tmp_path)
    (root / "agents" / "a-domain.md").write_text(
        render("a-domain", {}, "2026-09-17"), encoding="utf-8")

    found = _findings(root)

    assert len(found) == 1, f"the live renderer's output is not detected: {found}"
    assert found[0]["agent"] == "a-domain"


def test_a_reviewed_specialist_is_not_reported(tmp_path: Path) -> None:
    """The three OPEN sections filled in: the judgement was supplied."""
    root = _kit(tmp_path)
    body = render("a-domain", {}, "2026-09-17").replace("— OPEN", "— answered")
    (root / "agents" / "a-domain.md").write_text(body, encoding="utf-8")

    assert _findings(root) == []


def test_the_count_is_the_number_of_open_sections(tmp_path: Path) -> None:
    root = _kit(tmp_path)
    body = render("a-domain", {}, "2026-09-17")
    (root / "agents" / "a-domain.md").write_text(body, encoding="utf-8")

    message = _findings(root)[0]["message"]

    assert f"{body.count('— OPEN')} section(s)" in message, message
