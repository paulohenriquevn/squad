"""A rule linked to `../docs/` and the link resolved in the kit and nowhere else.

`docs/wiki/` is the kit's authored knowledge and `install.sh` does not copy it — deliberately:
`rules/README.md` places a file by who OWNS it, and a consumer owns none of that. So a rule
citing a decision document must use the absolute URL, which is what `cycle-release.md` and
`autonomy-envelope.md` already do.

Measured 2026-09-22 by the full slice runner, which was the only thing that could see it:
a relative link added to `current-constraint.md` resolved in this repository —
`rules/../docs/wiki/…` is `docs/wiki/…` — and resolved to `.claude/docs/` in an install,
where nothing writes. `check_xrefs --strict` passed HERE, `install.sh` exited 1 THERE, and
**43 tests failed from one link**, all of them in the install suite.

That is the shape `run_slice_tests.sh` names in its own banner: *red in an install and green
upstream is a different finding from red everywhere, and takes a different action.* The kit's
own checkout cannot see it by construction, which is why the check belongs here rather than
in the checker.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
RULES = _ROOT / "rules"

#: A markdown link target that climbs out of `rules/`. Climbing is NOT the defect —
#: `../skills/` and `../mechanisms/` land inside `.claude/` in an install and resolve
#: perfectly. What breaks is climbing into a directory the installer does not carry.
_ESCAPING_LINK = re.compile(r"\]\(\.\./([^)/]+)/[^)]*\)")

INSTALLER = _ROOT / "mechanisms" / "distribution" / "install.sh"

#: The line in `install.sh` that names every tree copied into a consumer. Read from the
#: installer rather than listed here: a second copy of what travels is a second thing to
#: keep in step, and this whole class of defect is one contract checked in two places.
#: Anchored with `\s*` rather than `^`: one of the three loops is nested inside a branch
#: and indented, and a pattern that missed it reported `agents/` as a tree the install does
#: not carry — flagging a link that resolves perfectly in both trees.
_COPY_LOOP = re.compile(r"^\s*for item in ([a-z ]+); do$", re.MULTILINE)


def travelling_trees() -> set[str]:
    loops = _COPY_LOOP.findall(INSTALLER.read_text(encoding="utf-8"))
    assert loops, "install.sh no longer declares its copied trees in a `for item in` loop"
    return {name for line in loops for name in line.split()}


def test_no_rule_links_into_a_tree_the_install_does_not_carry() -> None:
    travels = travelling_trees()
    offenders: list[str] = []
    for rule in sorted(RULES.glob("*.md")):
        for match in _ESCAPING_LINK.finditer(rule.read_text(encoding="utf-8")):
            if match.group(1) not in travels:
                offenders.append(f"{rule.name} -> ../{match.group(1)}/")

    assert offenders == [], (
        f"{offenders}: the link resolves in this checkout and points at nothing in an "
        f"install, where rules/ is .claude/rules/ and the installer carries only "
        f"{sorted(travels)}. Cite the absolute URL the sibling rules use"
    )


def test_the_trees_that_do_travel_are_not_flagged() -> None:
    """THE CONTROL. `../skills/` and `../mechanisms/` are cited by several rules and
    resolve in both trees; a check that flagged them would be one people route around."""
    travels = travelling_trees()

    assert {"skills", "mechanisms", "rules", "agents"} <= travels, sorted(travels)
    assert "docs" not in travels, "docs/ travels now; this whole test needs rewriting"


def test_the_sibling_rules_still_use_the_absolute_form() -> None:
    """THE CONTROL. If nothing links to the wiki at all, the test above passes over
    nothing and the convention it protects has quietly disappeared."""
    linking = [
        rule.name for rule in RULES.glob("*.md")
        if "github.com/paulohenriquevn/squad/blob/main/docs/wiki/" in
        rule.read_text(encoding="utf-8")
    ]

    assert len(linking) >= 2, f"only {linking} cite the wiki; the convention has no users"
