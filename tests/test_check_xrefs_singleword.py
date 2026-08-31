"""A single-word skill name had to be added to a hardcoded list by hand.

`_extract_cycle_phases` accepts `/kebab-case-names` by pattern, and single-word
names only if they appear in a literal alternation — `to-plan|implement|review|
release|trajectory-review|acceptance`. A new single-word skill is therefore
invisible to the orphan check until someone remembers to edit a regex, and the
symptom is a WARN that says the skill is unreferenced when the cycle rule
references it plainly.

That is the shape this kit has spent the week paying for: a rule implemented for
the cases its author happened to list. The fix is to ask the filesystem — a
single word is a skill name when `skills/<name>/` exists — which cannot go stale
and cannot admit a word that is not a skill.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_xrefs import _extract_cycle_phases  # noqa: E402

CYCLE = """# Cycle: X

## Chain

```
/pipeline B-014 B-022
     ↓ schedules items
/to-plan {slug}
     ↓
/implement
```
"""


def test_a_single_word_skill_that_exists_is_found() -> None:
    """`pipeline` is a directory under skills/. Nothing else need be true."""
    found = _extract_cycle_phases(CYCLE, skills_root=ROOT / "skills")
    assert "pipeline" in found


def test_kebab_and_listed_names_still_work() -> None:
    found = _extract_cycle_phases(CYCLE, skills_root=ROOT / "skills")
    assert {"to-plan", "implement"} <= found


def test_a_single_word_that_is_not_a_skill_is_not_claimed(tmp_path: Path) -> None:
    """Asking the filesystem must not become accepting anything.

    `/usr` or `/tmp` in a chain block is a path, not a skill, and reporting it as
    a missing skill would be a false positive in a checker consumers run.
    """
    found = _extract_cycle_phases(
        "## Chain\n\n```\n/usr/bin/thing\n/nonesuch arg\n```\n",
        skills_root=tmp_path)
    assert not found
