"""Routing decides which specialist reads the diff, and nothing pinned the threshold.

`detect_domain.py`'s exit-code block said "confidence >= 0.5 for primary" while `main`
applied 0.20 — and no test read either number, so the two could disagree indefinitely.
The file's own `_keyword_pattern` docstring records what one mis-route cost on a
consumer: "the two words the change was ABOUT sent it to a reviewer with nothing to
find, who reported clean".
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "skills" / "review" / "scripts" / "detect_domain.py"


def _detect(tmp_path: Path, plan_text: str) -> tuple[dict, int]:
    plan = tmp_path / "a-plan.md"
    plan.write_text(plan_text, encoding="utf-8")
    done = subprocess.run([sys.executable, str(_SCRIPT), "--plan", str(plan)],
                          capture_output=True, text=True, timeout=120, check=False)
    payload = json.loads(done.stdout[done.stdout.index("{"):]) if "{" in done.stdout else {}
    return payload, done.returncode


def test_the_documented_threshold_is_the_applied_one() -> None:
    """The header and `main` must name the same number."""
    source = _SCRIPT.read_text(encoding="utf-8")
    header = source.split('"""', 1)[1].split('"""', 1)[0]
    applied = source.split("primary_domain", 1)[1].split("\n", 1)[0]

    assert ">= 0.20" in applied, applied
    assert "0.20" in header, "the exit-code block names a threshold the code does not apply"
    assert "0.5" not in header.split("Exit codes:", 1)[1].split("\n\n", 1)[0]


def test_a_dominant_domain_is_detected(tmp_path: Path) -> None:
    plan_text = ("# Plan\n\n## Deep Dives\n"
                 + "- the database migration, the database schema, the database index\n" * 6)

    payload, code = _detect(tmp_path, plan_text)

    assert code == 0, payload
    assert payload["primary_domain"] != "unknown", payload


def test_hits_spread_below_the_floor_report_unknown(tmp_path: Path) -> None:
    """Exit 1 is also this, not only "no keyword hits" — which is what the header
    used to attribute it to, exclusively."""
    payload, code = _detect(tmp_path, "# Plan\n\nnothing recognisable at all here\n")

    assert payload.get("primary_domain") == "unknown", payload
    assert code == 1


def test_the_strongest_secondaries_survive_the_cap(tmp_path: Path) -> None:
    """Three secondaries are kept, and they are the three with the most hits.

    The list used to be built by iterating `confidence`, whose key order is the DOMAINS
    declaration order, and sliced [:3] without sorting — so with four domains over the
    threshold the three kept were whichever appear first in the literal, and a stronger
    signal declared later was dropped. Routing decides which specialist reads the diff.
    """
    import sys as _sys
    _sys.path.insert(0, str(_ROOT / "skills" / "review" / "scripts"))
    from detect_domain import rank_domains

    hits = {
        "auth": {"hits": 2},
        "api-design": {"hits": 2},
        "frontend": {"hits": 2},
        "database": {"hits": 40},
        "observability": {"hits": 30},
        "performance": {"hits": 20},
    }

    primary, secondaries, _ = rank_domains(hits)

    assert primary == "database"
    assert secondaries == ["observability", "performance"], secondaries
