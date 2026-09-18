"""VERA — the emitter. What it formats, and what it refuses to invent.

WHAT CHANGED, AND WHY THESE TESTS LOOK DIFFERENT
------------------------------------------------
`agents/vera-technical-arbiter.md` states the contract this module is held to:

    `mechanisms/fleet/vera.py` still owns the emission — the issue body, the
    labels, the schema. It is a formatter, and formatting is computation. You
    supply the judgement it used to fake.

The code did not implement that. It matched substrings against the problem text,
picked a lens from them, and returned one of five hard-coded solutions selected
by the lens alone — the solution never read the problem. Measured 2026-09-08
(#38): `--problem "typo in a variable name" --refs "app/main.py:57"` returned
`Size: t3` (a 1-2 week refactor) because `"57" in str(context)` matched the LINE
NUMBER, and `--problem "the secret is logged in plaintext"` proposed "Make
structure immediately obvious".

The suite that guarded it pinned that behaviour against fourteen items from one
consumer's registry, in Portuguese, in an English-by-policy repository — and one
of those items reads "costs 57 call sites", which is where the `"57"` literal
came from. A test written to make a defect pass is worse than no test; it was
deleted with the defect.

These assert the two things a formatter can be right or wrong about: that it
formats what it was given, and that it refuses to supply what it was not.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_FLEET = Path(__file__).resolve().parents[1] / "mechanisms" / "fleet"
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import vera  # noqa: E402 — post-bootstrap import

_SCRIPT = _FLEET / "vera.py"


def _judgement(**overrides: object) -> dict:
    base = dict(
        lens=vera.Lens.SOLID,
        severity=vera.Severity.HIGH,
        solution_title="Decouple the engine from the dashboard health check",
        what_changes="init() stops calling the dashboard; the check moves behind a port.",
        how_to_verify="The engine deploys with the dashboard down.",
        evidence="init() calls the dashboard health check before serving",
        refs=["api/internal/routes/engine/init.go:156"],
    )
    base.update(overrides)
    return base


# ── it formats what it is given ───────────────────────────────────────────────

def test_the_verdict_carries_the_judgement_it_was_handed() -> None:
    verdict = vera.emit("B-022", "Engine cannot deploy while the dashboard is down",
                        **_judgement())

    assert verdict.dominant_lens is vera.Lens.SOLID
    assert verdict.severity is vera.Severity.HIGH
    assert verdict.solution.title == "Decouple the engine from the dashboard health check"


def test_the_issue_body_carries_the_problem_the_evidence_and_the_references() -> None:
    verdict = vera.emit("B-022", "Engine cannot deploy while the dashboard is down",
                        **_judgement())

    issue = verdict.to_issue()

    assert "B-022" in issue["body"]
    assert "Engine cannot deploy while the dashboard is down" in issue["body"]
    assert "init() calls the dashboard health check" in issue["body"]
    assert "api/internal/routes/engine/init.go:156" in issue["body"]


def test_the_labels_restate_the_judgement_and_nothing_else() -> None:
    issue = vera.emit("B-022", "x", **_judgement()).to_issue()

    assert "severity:high" in issue["labels"]
    assert "lens:solid" in issue["labels"]
    assert issue["title"].startswith("[high]")


def test_the_rationale_is_the_principle_of_the_lens_not_an_analysis() -> None:
    """A canonical definition is computation; an analysis of the problem is not.

    Two different problems judged under the same lens get the same principle, and
    that is correct: the principle is a property of the lens. What used to vary
    with the problem text — the solution — no longer comes from here at all.
    """
    seen = set()
    for lens in vera.Lens:
        one = vera.emit("B-1", "a typo", **_judgement(lens=lens))
        other = vera.emit("B-2", "a secret in a log", **_judgement(lens=lens))

        assert one.rationale, f"{lens.name} has no principle text"
        assert one.rationale == other.rationale == vera._PRINCIPLE[lens]
        seen.add(one.rationale)

    assert len(seen) == len(vera.Lens), "two lenses share a principle"


# ── it refuses to invent the judgement ────────────────────────────────────────

def test_it_refuses_a_verdict_with_no_lens() -> None:
    with pytest.raises(vera.JudgementMissing):
        vera.emit("B-1", "x", **_judgement(lens=None))


def test_it_refuses_a_verdict_with_no_severity() -> None:
    with pytest.raises(vera.JudgementMissing):
        vera.emit("B-1", "x", **_judgement(severity=None))


def test_it_refuses_a_verdict_with_no_evidence() -> None:
    """"a verdict without them is a verdict about nothing" — mechanisms/README.md."""
    with pytest.raises(vera.JudgementMissing):
        vera.emit("B-1", "x", **_judgement(evidence="  "))


def test_it_refuses_a_verdict_with_no_file_reference() -> None:
    with pytest.raises(vera.JudgementMissing):
        vera.emit("B-1", "x", **_judgement(refs=[]))


def test_it_refuses_a_solution_that_does_not_say_what_changes() -> None:
    with pytest.raises(vera.JudgementMissing):
        vera.emit("B-1", "x", **_judgement(what_changes=""))


def test_it_refuses_a_solution_that_does_not_say_how_to_verify() -> None:
    with pytest.raises(vera.JudgementMissing):
        vera.emit("B-1", "x", **_judgement(how_to_verify=""))


# ── the defects that made this module a matcher ───────────────────────────────

def test_no_number_in_a_reference_can_decide_the_work_size() -> None:
    """`"57" in str(context)` made a typo a two-week refactor.

    Size is derived from something countable — how many places the fix touches —
    and from nothing else.
    """
    one = vera.emit("B-1", "typo in a variable name",
                    **_judgement(refs=["app/main.py:57"]))
    many = vera.emit("B-2", "typo in a variable name",
                     **_judgement(refs=[f"app/f{i}.py:1" for i in range(9)]))

    assert one.work_size is vera.WorkSize.T1
    assert many.work_size is vera.WorkSize.T3


def _executable_source() -> tuple[set[str], set[str]]:
    """Function names defined, and string literals evaluated, in the module.

    Read from the AST rather than the file, so the docstring may go on naming the
    defect it fixed — that history is the reason the fix is legible — while the
    assertion still speaks about what the module DOES.
    """
    import ast

    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    docstrings = {ast.get_docstring(node) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef))}
    names = {node.name for node in ast.walk(tree)
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    literals = {node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
                and node.value not in docstrings}
    return names, literals


def test_the_module_holds_no_keyword_table_to_guess_from() -> None:
    """The guessing has to be gone, not merely unused.

    A dormant matcher is one call site away from being the mechanism again, and
    the next reader cannot tell a dead branch from a live one.
    """
    names, literals = _executable_source()

    for banished in ("_detect_violations", "_assess_severity", "_estimate_work",
                     "_propose_solution"):
        assert banished not in names, f"{banished} still decides something here"
    assert "57" not in literals, "the magic literal that sized a typo as a refactor"


def test_the_module_ships_no_portuguese_default_strings() -> None:
    """These reached GitHub issue bodies in an English-by-policy repository."""
    _, literals = _executable_source()
    blob = " ".join(literals)

    for marker in ("detectada", "detectado", "falta clareza", "múltiplo"):
        assert marker not in blob


# ── the CLI ───────────────────────────────────────────────────────────────────

def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: PLW1510 — the returncode is the assertion
        [sys.executable, str(_SCRIPT), *args], capture_output=True, text=True,
    )


_CLI_JUDGEMENT = (
    "--problem", "Engine cannot deploy while the dashboard is down",
    "--evidence", "init() calls the dashboard health check",
    "--refs", "api/internal/routes/engine/init.go:156",
    "--lens", "solid",
    "--severity", "high",
    "--solution", "Decouple the engine from the dashboard health check",
    "--what-changes", "init() stops calling the dashboard",
    "--how-to-verify", "the engine deploys with the dashboard down",
)


def test_the_cli_emits_an_issue_when_the_judgement_is_supplied() -> None:
    done = _cli("B-022", *_CLI_JUDGEMENT, "--json")

    assert done.returncode == 0, done.stderr
    issue = json.loads(done.stdout)
    assert issue["title"].startswith("[high]")
    assert "B-022" in issue["body"]


def test_the_cli_refuses_rather_than_guessing_when_the_lens_is_absent() -> None:
    """It used to answer this invocation with a full verdict it had invented."""
    done = _cli("B-022",
                "--problem", "Engine cannot deploy while the dashboard is down",
                "--evidence", "init() calls the dashboard health check",
                "--refs", "api/internal/routes/engine/init.go:156")

    assert done.returncode != 0
    assert "lens" in done.stderr.lower()
