"""Every script a reviewer brief names must be one that runs.

The brief told reviewers: "`skills/plan-confidence/scripts/check_evidence_citations.py`
decides the question mechanically; run it before returning a plan on an unresolved
citation." That file has no `__main__` and no argparse — it is a library, imported by
`run_structural.py`. Running it prints nothing and exits 0.

Five readers followed the instruction and read that exit 0 as a pass: a peer session
four times, and the `vera-technical-arbiter` seat once, which recorded
"check_evidence_citations exits 0" inside a vote. None of them was careless. The
instruction was categorical and wrong.

The same note also claimed the checker "knows the prefix", while the detector's own
comment says it "Excludes paths containing slashes ... v0.1 keeps the regex
conservative". So the brief contradicted, with authority, a limit the detector states
about itself — which is worse than the narrow regex, because the regex is honest.

The invariant is deliberately blunt: a brief may not name a script path at all unless
that path has an entry point. Naming a library to a reviewer who has been told to act
mechanically is the defect, whatever the sentence around it says.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "mechanisms" / "cycle"))
sys.path.insert(0, str(_ROOT / "mechanisms" / "conventions"))

from panel_brief import _kit_root_note  # noqa: E402

# Any script path the note mentions, wherever it sits — the offending line named the
# module alone in backticks, and the replacement names one inside a command, so an
# anchored pattern would have stopped matching exactly when the text changed.
_PATH_RE = re.compile(r"([\w./-]*[\w-]+\.py)")


def _emitted_note(tmp_path: Path) -> str:
    """The note as a reviewer receives it — `_kit_root_note` emits only under `.claude/rules`."""
    contract = tmp_path / ".claude" / "rules" / "plan-confidence-golden-rule.md"
    contract.parent.mkdir(parents=True)
    contract.write_text("contract\n", encoding="utf-8")
    return _kit_root_note(contract)


def _has_entry_point(rel: str) -> bool:
    path = _ROOT / rel
    if not path.is_file():
        return False
    source = path.read_text(encoding="utf-8")
    return "__main__" in source or "argparse" in source


def test_the_note_is_emitted_at_all(tmp_path: Path) -> None:
    """A note that never renders would pass every assertion below vacuously."""
    assert "HOW PATHS IN THIS PROJECT RESOLVE" in _emitted_note(tmp_path)


def test_every_script_the_note_names_can_be_run(tmp_path: Path) -> None:
    note = _emitted_note(tmp_path)
    named = sorted(set(_PATH_RE.findall(note)))
    assert named, "the note names no script, so nothing here was checked"
    unrunnable = [rel for rel in named if not _has_entry_point(rel)]
    assert not unrunnable, (
        "the brief names a module a reviewer cannot run: "
        + ", ".join(unrunnable)
        + " — running a library prints nothing and exits 0, which reads as a pass"
    )
