"""The termination condition names commands, and nothing guaranteed they exist.

`compose_goal_condition.py` embute `/grill-me`, `/discover-plan`,
`/plan-confidence`, `/implement`, `/code-quality`, `/review` e `/acceptance`
as literal strings in the condition's text, each beside the artifact it must
produce. Rename or retire any one of them and the condition still composes, still
arms the Stop hook and still reads as authoritative — while telling the agent to
run a command that no longer exists.

`check_xrefs.py` does not cover this case: Check 7 sweeps `skills/**/*.py` for
references to `rules/*.md`, never to `/skill-name`. And history shows skill
retirement is real, not hypothetical — retiring the roadmap skills left 15
references mechanically replaced, one of them pointing at the
skill errada.

The failure mode is silent and late: the one who discovers it is the agent, in
the middle of an already-bound session, trying to satisfy an impossible
criterion.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "skills" / "cycle-goal" / "scripts" / "compose_goal_condition.py"

# `/foo-bar` in prose. Excludes paths (`/tmp/x`) by requiring hyphen-or-end and
# rejeitando um `/` logo depois.
_COMMAND_RE = re.compile(r"(?<![\w/.])/([a-z][a-z0-9]*(?:-[a-z0-9]+)*)(?![\w/-])")

# Tokens matching the shape that are not skill commands.
_NOT_COMMANDS = {"n", "a"}

# Claude Code CLI primitives — real, but never skills of this repository.
# `goal` is cited because the skill exists largely to explain why it does NOT use
# it (`SKILL.md § Why this does not use /goal`) and where it inherited the 4000
# character cap from. Forbidding the mention would force rewriting the explanation
# so it cannot name its own subject.
#
# The distinction that matters: a primitive cited in historical prose is a
# reference; a command printed in an error message is an instruction. It was the
# second shape that told the user to run `roadmap-init`, retired — which is why
# this allowlist is nominal and short, never a pattern absolving the whole
# category.
_CLI_PRIMITIVES = {"goal"}


def _existing_skills() -> set[str]:
    return {p.parent.name for p in (_REPO / "skills").glob("*/SKILL.md")}


def test_script_exists() -> None:
    # Arrange / Act / Assert — the whole test is vacuous if the target moved.
    assert _SCRIPT.is_file(), f"test target not found: {_SCRIPT}"


def test_every_command_named_in_the_condition_is_a_real_skill() -> None:
    # Arrange
    source = _SCRIPT.read_text(encoding="utf-8")
    skills = _existing_skills()

    # Act — every `/command` cited in the script, with the line it appears on.
    cited: dict[str, int] = {}
    for lineno, line in enumerate(source.split("\n"), 1):
        for match in _COMMAND_RE.finditer(line):
            name = match.group(1)
            if name in _NOT_COMMANDS or name in _CLI_PRIMITIVES:
                continue
            cited.setdefault(name, lineno)

    # Assert — none of them may be a command that does not exist.
    ghosts = {n: ln for n, ln in cited.items() if n not in skills}
    assert not ghosts, (
        "compose_goal_condition.py names commands with no matching skill "
        f"(name -> line): {ghosts}. The condition would compose and arm anyway, "
        "mandando o agente rodar algo inexistente."
    )


def test_no_user_facing_message_points_at_a_command_that_does_not_exist() -> None:
    """The primitives allowlist covers prose, never instruction.

    `_CLI_PRIMITIVES` exempts historical mentions in docstrings and comments. A
    message printed to the user is another thing: it says what to do NOW. That is
    exactly the shape that told people to run `roadmap-init` after its retirement.
    Nothing is exempt here — if it is in a `print`, it must exist.
    """
    # Arrange
    source = _SCRIPT.read_text(encoding="utf-8")
    skills = _existing_skills()
    tree = ast.parse(source)

    # Act — every string literal that reaches a `print(...)`.
    printed: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print"):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                printed.append((sub.value, node.lineno))

    # Assert
    ghosts: dict[str, int] = {}
    for text, lineno in printed:
        for match in _COMMAND_RE.finditer(text):
            name = match.group(1)
            if name in _NOT_COMMANDS or name in skills:
                continue
            ghosts.setdefault(name, lineno)

    assert not ghosts, (
        "a message printed to the user names a non-existent command "
        f"(name -> print line): {ghosts}. A remedy that does not exist is worse "
        "than none: it sends people searching instead of resolving."
    )


def test_the_condition_actually_names_the_pipeline() -> None:
    """Guarda contra o teste acima passar por vacuidade.

    If a refactor replaces the literals with interpolation, the previous test goes
    green while verifying nothing. This one demands the backbone is still there.
    """
    # Arrange
    source = _SCRIPT.read_text(encoding="utf-8")

    # Act / Assert
    for command in ("/implement", "/code-quality", "/review", "/acceptance"):
        assert command in source, (
            f"{command} vanished from the condition text — if that was intentional, "
            "atualize `requires` em skills/cycle-goal/SKILL.md junto"
        )
