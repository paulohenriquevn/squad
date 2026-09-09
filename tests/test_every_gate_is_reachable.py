"""A gate nobody runs reports its first real failure to nobody.

Measured on 2026-09-02: of eighteen gates, two were executed by nothing at all —
not the CI, not a hook, not `verify_ecosystem`, not any script.
`check_orphan_verdicts` appeared exactly once outside its own tests, inside a
COMMENT in a sibling gate. Both passed clean when finally run, so nothing was
hiding behind them; that is luck, and luck is not a property you can rely on
twice.

The two they check are not minor. One asks whether every verdict a cycle rule
declares can actually be emitted by something; the other asks whether every
declared phase has an emitter at all. A verdict named in a rule and produced by
nothing is a state the chain can never enter, and a reader planning around it is
planning around a state that does not exist — `NEEDS_SPLIT` lived exactly that
way, documented and unimplemented, and briefs needing a split were squeezed into
BLOCKED.

Amended (#23, 2026-09-03) — the same lens missed `check_install_drift`. Nine
prose mentions in production files (comments and docstrings) matched the
`<gate>.py` pattern the same way a `subprocess.run([..., "<gate>.py"])` call
does, so the sweep reported three "callers" that were entirely narrative.
Stripping Python `#` comments, Python triple-quoted string literals, and shell
`#` comments before the regex runs closes that hole: the test now sees code,
not prose. The gate spent ten hours undetected because of this exact loophole,
so the fix is to the lens itself rather than a fourth reader of the same
question.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_GATES = _REPO / "mechanisms" / "gates"

#: Gates that legitimately have no automatic trigger, each with the reason.
#: Empty on purpose — an entry here is a claim that a gate should never fire on
#: its own, and that claim should be hard to make.
MANUAL_ONLY: dict[str, str] = {}


#: Match a Python triple-quoted string in its four flavours (plain, r-, b-, u-,
#: f-) and either quote kind. Non-greedy so nested triple-quotes do not lump.
_PY_TRIPLE = re.compile(
    r'''(?xs)
        (?:[rRbBuUfF]{0,2})            # optional string prefix
        (?:
            """.*?"""
          |
            '\'\''.*?'\'\''
        )
    '''
)

#: A `#` that starts a comment: at line start (optional indent), or after
#: whitespace / `;` / `&` / `|`. This keeps a `#` inside a string alone,
#: which is why we do NOT strip inline `#`s that follow a non-space glyph.
_LINE_COMMENT = re.compile(r'(?m)(^[ \t]*|[ \t;&|])#[^\n]*')


def _strip_python_prose(text: str) -> str:
    """Drop triple-quoted string literals and `#` line comments.

    Preserves every other byte — including single-quoted string literals like
    `"check_x.py"` inside a subprocess call — because the regex that follows
    depends on real spacing (`_run_gate(...)` with no space between name and
    paren). A tokenize-based rewrite loses that spacing and breaks the regex,
    which is how the first attempt at this fix registered `_run_gate` and
    `("check_orphan_verdicts"` as separated by whitespace.
    """
    text = _PY_TRIPLE.sub("", text)
    return _LINE_COMMENT.sub(lambda m: m.group(1), text)


def _strip_shell_prose(text: str) -> str:
    """Drop `#` line comments in shell scripts.

    Anchored to line start or a shell-word boundary so a `#` glued to a real
    token (a URL fragment, a variable expansion) is left alone.
    """
    return _LINE_COMMENT.sub(lambda m: m.group(1), text)


def _stripped(text: str, path: Path | str) -> str:
    """Return `text` with prose stripped according to `path`'s language."""
    suffix = Path(path).suffix
    if suffix == ".py":
        return _strip_python_prose(text)
    if suffix == ".sh":
        return _strip_shell_prose(text)
    return text


def _gate_names() -> list[str]:
    return sorted({p.stem for p in _GATES.glob("check_*.py")}
                  | {"validate_skill_frontmatter"})


def _invokes(text: str, gate: str) -> bool:
    """A real invocation, not a mention.

    `check_orphan_verdicts` was named in a COMMENT in a sibling gate, and that
    read as coverage until someone looked — so a bare occurrence of the name does
    not count. What counts is the filename, an import, or the name passed as an
    argument to a runner (`_run_gate(dir, "check_x")`), which is how a dispatcher
    invokes a gate whose path it builds itself.
    """
    return bool(re.search(
        rf"{gate}\.py|from {gate} import|import {gate}\b|_run_gate\([^)]*[\"']{gate}[\"']",
        text))


def _triggers_for(gate: str) -> list[str]:
    sources: list[tuple[str, str]] = []
    workflows = _REPO / ".github" / "workflows"
    if workflows.is_dir():
        for path in workflows.glob("*.yml"):
            sources.append((f"CI:{path.name}", path.read_text(encoding="utf-8")))
    for path in (list((_REPO / "hooks").glob("*.py"))
                 + list((_REPO / "mechanisms").rglob("*.py"))
                 + list((_REPO / "mechanisms").rglob("*.sh"))
                 + list((_REPO / "skills").rglob("scripts/*.py"))):
        if path.stem == gate or "/tests/" in str(path):
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        sources.append((str(path.relative_to(_REPO)), _stripped(raw, path)))
    return [name for name, text in sources if _invokes(text, gate)]


@pytest.mark.parametrize("gate", _gate_names())
def test_something_runs_this_gate(gate: str) -> None:
    """Being correct is not the same as being consulted."""
    if gate in MANUAL_ONLY:
        pytest.skip(f"declared manual-only: {MANUAL_ONLY[gate]}")

    triggers = _triggers_for(gate)

    assert triggers, (
        f"{gate} is executed by nothing — not the CI, not a hook, not "
        f"verify_ecosystem, not any script. Wire it, or add it to MANUAL_ONLY "
        f"with the reason it should never fire on its own.")


def test_the_two_phase_gates_are_wired_into_the_verifier() -> None:
    """Named specifically because they were the two found orphaned, and because
    a general assertion is satisfied by any caller — including a weak one."""
    verifier = (_GATES / "verify_ecosystem.py").read_text(encoding="utf-8")

    for gate in ("check_orphan_verdicts", "check_phase_emitters"):
        assert _invokes(verifier, gate), f"{gate} left the verifier again"
    assert '("Orphan verdicts"' in verifier and '("Phase emitters"' in verifier, \
        "wired but not registered in the check list is the same as not wired"
