r"""A refusal that names no destination makes the reader invent one.

`boundaries.violation` refuses a write into an installed kit and says *"Send it to the
kit's own repository instead."* Correct, and incomplete: it does not say WHERE that is,
or how a consumer reaches it.

MEASURED, 2026-09-21. A consumer session hit this refusal while trying to install a check
it had just written. Following the instruction cost it: finding the kit's path, reading
`git-safety.md` to learn a second agent may not join an occupied tree, discovering the
tree WAS occupied (`git status --porcelain` showing ten dirty files), concluding a branch
was not the escape either — and finally writing a backlog item of its own, B-246, whose
whole subject is the logistics of moving a file between two repositories.

None of that is the work. The kit HAS a registry for exactly this — `kit_issues.py`
reads the issues a fleet may take — and the refusal never mentioned it.

WHAT A GOOD REFUSAL OWES

The same thing this kit demands of its own gates everywhere else: name the next action.
`check_deps_audit` was corrected on the same principle hours earlier — it told readers to
write an allowlist entry into a file nothing read. A remedy that does not work when
followed is worse than no remedy, because it spends the reader's time before failing.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from squad.boundaries import violation  # noqa: E402
from squad.layout import Layout  # noqa: E402


def _refusal(tmp_path: Path) -> str:
    kit = tmp_path / ".claude"
    (kit / "mechanisms" / "gates").mkdir(parents=True)
    layout = Layout(kit_dir=kit, eco=kit, project_dir=tmp_path, kind="plugin")
    message = violation(kit / "mechanisms" / "gates" / "check_new.py", layout)
    assert message, "the premise: writing into an installed kit is refused"
    return message


def test_the_refusal_names_the_registry_that_receives_it(tmp_path: Path) -> None:
    """`kit_issues.py` exists for this and the refusal never said so."""
    message = _refusal(tmp_path)

    assert "issue" in message.lower(), (
        f"the refusal says where NOT to write and not where the fix goes: {message}"
    )


def test_the_refusal_does_not_send_a_reader_into_an_occupied_tree(tmp_path: Path) -> None:
    """The instruction that cost a consumer an afternoon.

    "Send it to the kit's own repository" reads as "go and commit there", and
    `git-safety.md` forbids a second agent in one working tree. A refusal that names an
    action the rules then refuse is a refusal that has not finished thinking.
    """
    message = _refusal(tmp_path)
    lowered = message.lower()

    # The INSTRUCTION, not the explanation. The refusal may — and does — say that
    # "send it upstream" is not the same as "go and commit there", because naming the
    # confusion is how it stops being made. What it must not do is issue that as the
    # action, so the check is on what appears under WHERE IT GOES.
    where = lowered.split("where it goes:", 1)[-1].split("project-owned")[0]

    assert "issue" in where, f"the destination is not an issue: {where}"
    assert "clone" not in where and "checkout the kit" not in where, where


def test_the_refusal_still_says_what_stays_writable(tmp_path: Path) -> None:
    """The half that already worked must not be lost to the half being added."""
    message = _refusal(tmp_path)

    for owned in ("rules/*.txt", "agents/", "settings.json"):
        assert owned in message, f"{owned} vanished from the refusal"
