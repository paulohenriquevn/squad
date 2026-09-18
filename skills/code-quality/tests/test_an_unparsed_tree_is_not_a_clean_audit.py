"""D2 reported CLEAN over sources its parser never read.

`extract_imports_and_calls` returned `[]` for "this file imports nothing" AND for every
way the parse can fail — tree-sitter absent, the grammar failing to load, the file
unreadable, a malformed source, a per-language extractor bug. Three of the four D2
detectors took the empty list at face value. Measured on the build droplet: 0 symbols
from a 1600-line file carrying ten `use` statements, and the audit emitted PASS.

`rust.py` alone carried a vacuity guard, inferred from "a source has an import line and
nothing was extracted anywhere". `extract_checked` reports the fact itself, and the other
three now use it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SKILL))

from scripts.check_symbol_fab import extract_checked  # noqa: E402 — post-bootstrap import


def test_a_file_that_could_not_be_read_says_the_parse_did_not_happen(tmp_path: Path) -> None:
    symbols, parsed = extract_checked(tmp_path / "nothing-here.py", "python")

    assert symbols == []
    assert parsed is False


def test_a_file_that_was_read_says_the_parse_happened(tmp_path: Path) -> None:
    src = tmp_path / "mod.py"
    src.write_text("import os\n", encoding="utf-8")

    symbols, parsed = extract_checked(src, "python")

    assert parsed is True, "a readable source reported as unparsed"
    assert symbols, "the parse ran and extracted nothing from `import os`"


@pytest.mark.parametrize("lang,module", [
    ("python", "detectors.python"),
    ("go", "detectors.go"),
    ("typescript", "detectors.typescript"),
])
def test_a_detector_whose_parser_never_ran_reports_unavailable_not_clean(
        lang: str, module: str, tmp_path: Path, monkeypatch) -> None:
    """The finding the guard must emit, in each of the three detectors that lacked it."""
    import importlib

    mod = importlib.import_module(f"scripts.{module}")
    monkeypatch.setattr(mod, "extract_checked", lambda *_a, **_k: ([], False))

    src = tmp_path / f"file.{ 'py' if lang == 'python' else lang[:2] }"
    src.write_text("x\n", encoding="utf-8")

    # By the language it declares, not by the name: `BaseDetector` is imported into
    # each of these modules and its methods raise NotImplementedError.
    detector = next(
        getattr(mod, name)() for name in dir(mod)
        if isinstance(getattr(mod, name), type)
        and getattr(getattr(mod, name), "language", None) == lang
    )
    findings = detector.detect_symbol_fabrication([src])

    assert findings, f"{lang}: an unparsed tree produced no finding at all — a silent clean"
    assert any("did not run" in f.message for f in findings), [f.message for f in findings]
    assert all(f.severity == "SOFT_CAP" for f in findings)


# ── D5 findings must be nameable ─────────────────────────────────────────────


@pytest.mark.parametrize("make,expected", [
    (lambda arch, lang: arch.violation(lang, tool="import-linter", rule="no-cycles",
                                       file_path="a.py", symbol_or_line="12",
                                       message="domain imports infra"),
     "architecture_violation_python"),
    (lambda arch, lang: arch.vacuous_rule(lang, tool="import-linter", rule="no-cycles",
                                          config_path=".importlinter",
                                          detail="module gone"),
     "vacuous_architecture_rule_python"),
])
def test_a_d5_finding_resolves_to_a_stable_identifier(make, expected) -> None:
    """D5 fell through to the EMPTY STRING.

    `_arch.violation` and `_arch.vacuous_rule` both emit HARD findings and every language
    detector runs D5, so a FAIL_HARD verdict could be reached by a finding whose stable
    identifier was `""`. Nothing downstream can allowlist, cite or dismiss an empty
    identifier — a cap nobody can name is a cap nobody can act on.
    """
    from scripts._detector_contract import _finding_to_stable_identifier
    from scripts.detectors import _arch

    finding = make(_arch, "python")

    assert _finding_to_stable_identifier(finding) == expected, (
        f"D5 resolved to {_finding_to_stable_identifier(finding)!r}")


def test_the_two_d5_shapes_do_not_share_an_identifier() -> None:
    """They take opposite actions: fix the code, versus delete a rule that cannot fire."""
    from scripts._detector_contract import _finding_to_stable_identifier
    from scripts.detectors import _arch

    broken = _arch.violation("go", tool="go-arch-lint", rule="r", file_path="a.go",
                             symbol_or_line="1", message="m")
    vacuous = _arch.vacuous_rule("go", tool="go-arch-lint", rule="r",
                                 config_path="c.yml", detail="d")

    assert _finding_to_stable_identifier(broken) != _finding_to_stable_identifier(vacuous)


def test_the_report_is_written_before_the_json_that_publishes_its_path() -> None:
    """`summary["report_path"]` was assigned AFTER the payload was serialised.

    The JSON was built, written and printed, and the key was then set on a dict nobody
    read again. `SKILL.md` Step 5 lists `report_path` in the contract `/plan-confidence`
    and `/implement` consume, so every consumer saw the key missing while the report sat
    on disk beside them.

    Asserted on ORDER rather than end to end: the orchestrator needs the kit's whole
    `rules/` tree to run at all, and a fixture that installs the kit to check one key
    ordering costs more than it proves. Order is structure, and structure survives a
    rewrite — `_write_markdown_report` moving back below the serialisation fails here.

    Read from `_write_report`, where both statements moved when `_emit_and_exit` was
    split. The invariant is the same one; it just lives in a smaller function now.
    """
    import inspect

    from scripts import run_code_quality

    body = inspect.getsource(run_code_quality._write_report)
    wrote_report = body.index("_write_markdown_report(")
    serialised = body.index("json.dumps(summary")

    assert wrote_report < serialised, (
        "the JSON is serialised before the report it claims to point at, so "
        "`report_path` is assigned into a dict nobody reads again")



# ── the merge must read the verdict, not a defaulted cap ─────────────────────


def test_a_fail_hard_summary_with_no_score_cap_still_forces_invalid() -> None:
    """The short-circuit read `score_cap` with a default of 100.

    That default is what happens whenever the key is ABSENT — so a summary carrying
    `verdict: FAIL_HARD` and no `score_cap` returned before the FAIL_HARD branch ever
    ran, and the plan kept its own SHIPPABLE verdict over code the audit had failed hard.
    A missing key is not a passing score.
    """
    from scripts.cq_invoke import merge_verdict_into_plan_confidence

    plan = {"verdict": "SHIPPABLE", "final_score_after_caps": 95,
            "hard_caps_triggered": []}

    merge_verdict_into_plan_confidence(plan, {"verdict": "FAIL_HARD"})

    assert plan["verdict"] == "INVALID", plan
    assert plan["final_score_after_caps"] <= 49, plan


def test_a_passing_summary_with_no_score_cap_changes_nothing() -> None:
    """The fix must not cap a plan whose audit passed."""
    from scripts.cq_invoke import merge_verdict_into_plan_confidence

    plan = {"verdict": "SHIPPABLE", "final_score_after_caps": 95,
            "hard_caps_triggered": []}

    merge_verdict_into_plan_confidence(plan, {"verdict": "PASS"})

    assert plan["verdict"] == "SHIPPABLE"
    assert plan["final_score_after_caps"] == 95
