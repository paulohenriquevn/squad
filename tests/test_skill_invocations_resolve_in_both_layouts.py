"""A command in a SKILL.md that only runs in the kit's own repository.

`python3 skills/acceptance/scripts/extract_acceptance_criteria.py` resolves at
the kit's root and nowhere else. In a plugin install the same file is at
`.claude/skills/…`, so an agent following the instruction verbatim runs python3
against a path that does not exist.

Reported by a consumer session on 2026-08-29, caught by that repository's own
`skill-script-paths` gate: 25 invocations across 8 skills, blocking its push. A
sweep here found 32 across 14 files, because the gate looks at `skills/` and the
kit also writes bare `scripts/`.

WHY THIS IS THE WORST OF THE FAMILY
-----------------------------------
Eight defects today share one root — a path written against the standalone
layout. Six were preservation, two were checkers reading the wrong directory. In
every one of those a MACHINE got the wrong answer and something eventually said
so. This one is different: it is an INSTRUCTION TO AN AGENT. Nothing validates
it, nothing reports it, and the failure surfaces as a confused agent improvising
around a missing file.

The rule, not the cases: no invocation in any markdown the kit ships may assume
which layout it is running in.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: `python3 skills/…` or `bash mechanisms/…` with no layout resolution in front.
#: The negative lookbehind lets the fixed form through: once the path is prefixed
#: by a `$ECO`-style expansion or `.claude/`, it is no longer layout-blind.
_BLIND = re.compile(
    r'(?<![$/"\w])(?:python3|bash|sh)\s+(?!["\']?\$)(skills|mechanisms|hooks)/[A-Za-z0-9_./-]+'
)

#: Markdown the kit ships and an agent is expected to follow.
#:
#: The ecosystem-root files were missing from the first sweep, and a consumer's
#: gate found five more invocations in `HOW-TO-USE.md` — the file a person opens
#: FIRST to learn the kit. That omission is the same shape as the defect being
#: fixed: a sweep declared complete while covering the directories the author
#: happened to think of.
_SHIPPED = (
    "skills/*/SKILL.md", "skills/*/reference/*.md",
    "rules/*.md", "commands/*.md",
    "*.md",  # HOW-TO-USE, README, CONTRIBUTING, SECURITY
)

#: Two root files are exempt, for different reasons, and both are measured rather
#: than assumed — `install.sh` copies `HOW-TO-USE.md` and `README.md` into a
#: consumer and does not copy these:
#:
#: `CHANGELOG.md` QUOTES the broken form as evidence — "the freshly written Step 2
#: invoked `python3 skills/backlog-item/…`" is a record of a defect, not an
#: instruction to follow. Rewriting it would edit history to make a checker quiet,
#: which is the one thing a changelog must never do.
#:
#: `CONTRIBUTING.md` addresses someone working ON the kit, in its own repository,
#: where `bash mechanisms/cycle/run_slice_tests.sh` is the correct command and the layout
#: expression would be noise. It never reaches a consumer, so it cannot mislead
#: one.
_EXEMPT = {"CHANGELOG.md", "CONTRIBUTING.md"}


def _offenders() -> list[tuple[Path, int, str]]:
    out: list[tuple[Path, int, str]] = []
    for pattern in _SHIPPED:
        for path in ROOT.glob(pattern):
            if path.name in _EXEMPT:
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if _BLIND.search(line):
                    out.append((path.relative_to(ROOT), n, line.strip()))
    return out


def test_no_shipped_instruction_assumes_a_layout() -> None:
    """The rule. A consumer following the kit's own docs must not hit a missing file."""
    offenders = _offenders()
    assert not offenders, (
        f"{len(offenders)} invocation(s) resolve in only one layout:\n" +
        "\n".join(f"  {p}:{n}  {t[:88]}" for p, n, t in offenders[:12]) +
        (f"\n  ... and {len(offenders) - 12} more" if len(offenders) > 12 else "") +
        "\n\nUse the form that resolves in both:\n"
        '  python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/…"'
    )


def test_the_detector_accepts_the_fixed_form(tmp_path: Path) -> None:
    """A guard that flagged the fix would be worse than no guard."""
    fixed = 'python3 "$([ -d .claude/skills ] && echo .claude || echo .)/skills/x/scripts/y.py"'
    assert not _BLIND.search(fixed), "the corrected form is flagged as an offender"
    assert not _BLIND.search('python3 "$ECO/skills/x/scripts/y.py"')
    assert not _BLIND.search("python3 .claude/skills/x/scripts/y.py")


def test_the_detector_still_catches_the_defect() -> None:
    """And one that stopped catching it would be worse still."""
    assert _BLIND.search("python3 skills/acceptance/scripts/extract.py")
    assert _BLIND.search("bash mechanisms/distribution/install.sh")
