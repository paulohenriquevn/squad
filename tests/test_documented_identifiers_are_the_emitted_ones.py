"""A stable identifier a document names must be the one the code emits.

`plan-confidence/SKILL.md` says outright that "the stable identifiers above are what
appears in the JSON output's `hard_caps_triggered` list", then names `tdd_in_bugfix`
and `citation_fabricated`. `_detect_hard_caps` appends `bugfix_without_tdd` and
`fabricated_citation`. A consumer filtering `hard_caps_triggered` for the documented
spelling matched nothing — the silent kind of wrong, because an empty match reads as
"the cap never fired".

The same section lists two INVALID caps while the scorer forces INVALID on five.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SKILL = _ROOT / "skills" / "plan-confidence" / "SKILL.md"
_SCORER = _ROOT / "skills" / "plan-confidence" / "scripts" / "run_structural.py"


def _documented_identifiers() -> set[str]:
    section = _SKILL.read_text(encoding="utf-8").split("## Hard Caps", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"Stable identifier: `([a-z0-9_]+)`", section))


def _emitted_identifiers() -> set[str]:
    """Every stable id the scorer can put in `hard_caps_triggered`."""
    # Some ids are appended indirectly, as `<check>.stable_id`, so the sibling
    # checkers are read too: the question is which strings can REACH the list, not
    # which literals sit next to the append.
    scripts = [_SCORER, *sorted(_SCORER.parent.glob("check_*.py"))]
    emitted: set[str] = set()
    for script in scripts:
        source = script.read_text(encoding="utf-8")
        emitted |= set(re.findall(
            r'(?:triggered|hard_cap_ids)\.append\(\s*\(?\s*["\']([a-z0-9_]+)["\']', source))
        emitted |= set(re.findall(r'stable_id\s*=\s*["\']([a-z0-9_]+)["\']', source))
    return emitted


def test_every_documented_identifier_is_one_the_scorer_emits() -> None:
    documented, emitted = _documented_identifiers(), _emitted_identifiers()

    assert documented, "the parser found no documented identifiers — it lost its subject"
    assert documented - emitted == set(), (
        f"documented and never emitted: {sorted(documented - emitted)}")


def test_every_cap_that_forces_invalid_is_documented() -> None:
    source = _SCORER.read_text(encoding="utf-8")
    invalid_block = re.search(r"_INVALID_CAPS\b[^=]*=(.*?)\)\n", source, re.DOTALL)

    assert invalid_block, (
        "the set of caps that force INVALID is spread through the code, so no document "
        "can be checked against it; name it once")
    named = set(re.findall(r'["\']([a-z0-9_]+)["\']', invalid_block.group(1)))
    assert named - _documented_identifiers() == set(), (
        f"forces INVALID and absent from SKILL.md: {sorted(named - _documented_identifiers())}")
