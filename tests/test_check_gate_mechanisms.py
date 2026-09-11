"""Every declared hard gate names the mechanism that computes it.

THE DEFECT THIS CLOSES
----------------------
Measured on 2026-08-27 across the nine `rules/cycle-*.md` files carrying a
`## Hard gates` section: **61 gates declared, 11 naming a script, 50 naming
nothing**.

The 50 are not unenforced. Sampling the five BLOCKERs of `cycle-review.md`
against the hooks: secrets, trunk commits, `Co-Authored-By` and the CHANGELOG
are all mechanized (`stop-validation.py`, `validate-command.py`); only "failing
tests" is covered elsewhere (`/implement`, and CI). So four of five run, and
**zero of five say so**.

That is the defect. A mechanized gate whose rule names no mechanism is
indistinguishable, to the reader, from a gate nobody enforces — and both wrong
readings are expensive. This repository already recorded one direction:

    "A gate listed among four automatic ones reads as automatic, and a gate
    believed to be automatic is a gate nobody runs."

The other direction costs a person re-running by hand what a script already
did, or quietly ignoring the line.

WHAT COUNTS AS NAMING A MECHANISM
---------------------------------
One of three, and nothing else:

1. An executable that exists in this repository (`check_wiring.py`,
   `stop-validation.py`) cited in backticks.
2. A pointer to another rule's gate section, for a gate this rule does not own.
3. An explicit `_(not mechanized: <reason>)_` marker.

The third is the one that makes the check honest rather than decorative. A gate
that genuinely depends on human judgement — `/backlog-item`'s G3/G4/G5 are
judgement by design — must be allowed to say so. Forcing every line to name a
script would push someone to invent one, which is the failure mode above with
extra steps.

WHY A FABRICATED MECHANISM IS THE HARDER FAILURE
------------------------------------------------
Naming a script that does not exist is worse than naming none: it converts an
absent gate into a gate the reader believes was verified, and the belief is
what the whole rule set trades on. Same class as `fabricated_evidence`, which
this ecosystem caps a plan at 49 for.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "mechanisms" / "gates"))

from check_gate_mechanisms import check_gate_mechanisms  # noqa: E402


def _rules(tmp_path: Path, name: str, body: str) -> Path:
    rules = tmp_path / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    (rules / name).write_text(body, encoding="utf-8")
    return tmp_path


def _with_script(root: Path, relative: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# stub\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The three accepted forms
# ---------------------------------------------------------------------------

def test_a_gate_naming_an_existing_script_passes(tmp_path: Path) -> None:
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "- Every task has an executable RED shape — `check_tdd_shape.py`.\n"
    ))
    _with_script(root, "skills/implement/scripts/check_tdd_shape.py")

    report = check_gate_mechanisms(root)

    assert report.findings == []
    assert report.total_gates == 1
    assert report.named == 1


def test_a_gate_naming_an_existing_hook_passes(tmp_path: Path) -> None:
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "- New secrets committed — `stop-validation.py`.\n"
    ))
    _with_script(root, "hooks/stop-validation.py")

    assert check_gate_mechanisms(root).findings == []


def test_a_gate_pointing_at_another_rules_section_passes(tmp_path: Path) -> None:
    """A gate this cycle does not own cites its owner instead of duplicating it.

    `cycle-release.md` does exactly this for the single-flip invariant, which
    `cycle-acceptance.md` owns. Two copies of one invariant is the duplication
    this repository has already paid for once.
    """
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "- Single-flip invariant — owned by [`cycle-acceptance § Hard gates`]"
        "(cycle-acceptance.md).\n"
    ))
    # The owning rule carries the real gate, named. A fixture that leaves it
    # unnamed would fail for the owner's sake, not the pointer's.
    _rules(root, "cycle-acceptance.md",
           "# Acceptance\n\n## Hard gates\n\n- The flip — `flip_milestone_checkbox.py`.\n")
    _with_script(root, "skills/release/scripts/flip_milestone_checkbox.py")

    assert check_gate_mechanisms(root).findings == []


def test_an_explicitly_unmechanized_gate_passes(tmp_path: Path) -> None:
    """Judgement gates must be allowed to declare themselves as judgement."""
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "- Single domain — the description spans two domains. "
        "_(not mechanized: judgement — splitting a description is not a "
        "decision a regex can make)_\n"
    ))

    report = check_gate_mechanisms(root)

    assert report.findings == []
    assert report.unmechanized == 1
    assert report.named == 0


def test_an_unmechanized_marker_without_a_reason_fails(tmp_path: Path) -> None:
    """`_(not mechanized)_` bare is an escape hatch; with a reason it is a record."""
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n- Single domain. _(not mechanized)_\n"
    ))

    findings = check_gate_mechanisms(root).findings

    assert len(findings) == 1
    assert findings[0].kind == "unmechanized_without_reason"


# ---------------------------------------------------------------------------
# The failures
# ---------------------------------------------------------------------------

def test_a_gate_naming_nothing_is_reported(tmp_path: Path) -> None:
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n- Failing tests on the working branch.\n"
    ))

    findings = check_gate_mechanisms(root).findings

    assert len(findings) == 1
    assert findings[0].kind == "gate_without_mechanism"
    assert findings[0].rule == "cycle-demo.md"
    assert "Failing tests" in findings[0].gate


def test_a_gate_naming_a_script_that_does_not_exist_is_reported(tmp_path: Path) -> None:
    """The harder failure: an absent gate the reader believes was verified."""
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n- Coverage floor — `check_coverage_floor.py`.\n"
    ))

    findings = check_gate_mechanisms(root).findings

    assert len(findings) == 1
    assert findings[0].kind == "fabricated_mechanism"
    assert "check_coverage_floor.py" in findings[0].detail


def test_a_pointer_to_a_rule_that_does_not_exist_is_reported(tmp_path: Path) -> None:
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "- Owned by [`cycle-ghost § Hard gates`](cycle-ghost.md).\n"
    ))

    findings = check_gate_mechanisms(root).findings

    assert len(findings) == 1
    assert findings[0].kind == "fabricated_mechanism"


# ---------------------------------------------------------------------------
# Parsing: what is and is not a gate line
# ---------------------------------------------------------------------------

def test_a_table_header_is_not_a_gate(tmp_path: Path) -> None:
    """`| # | Gate | Blocks on |` describes the table; it declares no gate.

    The first version of the measurement counted these and inflated the total by
    three across the real rules.
    """
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "| # | Gate | Blocks on |\n"
        "|---|---|---|\n"
        "| G1 | **Routes** | `route_domain.py` refuses the repo. |\n"
    ))
    _with_script(root, "mechanisms/cycle/route_domain.py")

    report = check_gate_mechanisms(root)

    assert report.total_gates == 1, "the header and separator are not gates"
    assert report.findings == []


def test_prose_between_gates_is_not_a_gate(tmp_path: Path) -> None:
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "The loop refuses to start until these hold.\n\n"
        "- Everything is fine — `stop-validation.py`.\n"
    ))
    _with_script(root, "hooks/stop-validation.py")

    assert check_gate_mechanisms(root).total_gates == 1


def test_every_hard_gate_section_of_a_rule_is_swept(tmp_path: Path) -> None:
    """`cycle-implement.md` carries four `## Hard gates (...)` sections."""
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n"
        "## Hard gates (pre-loop)\n\n- One — `a.py`.\n\n"
        "## Hard gates (per iteration)\n\n- Two — `b.py`.\n\n"
        "## Output\n\n- Not a gate at all.\n"
    ))
    _with_script(root, "scripts/a.py")
    _with_script(root, "scripts/b.py")

    report = check_gate_mechanisms(root)

    assert report.total_gates == 2, "sections outside Hard gates are not swept"


def test_a_rule_with_no_hard_gates_section_contributes_nothing(tmp_path: Path) -> None:
    root = _rules(tmp_path, "cycle-demo.md", "# Demo\n\n## Output\n\n- A record.\n")
    assert check_gate_mechanisms(root).total_gates == 0


def test_a_subsection_does_not_truncate_the_hard_gates_section(tmp_path: Path) -> None:
    """A coverage gate that loses coverage without saying so is the failure it
    exists to prevent, one level up.

    Sibling `check_orphan_verdicts.py` fixed the same defect on 2026-08-31 with
    the measurement in its own comment: adding a `###` under a `## Verdicts`
    table dropped its swept count from 51 to 49 with no finding and nothing in
    the output to notice. This sweep's regex was still the pre-fix form until
    this test forced it up.

    A rule that carries a `### subsection` inside a `## Hard gates` section must
    have the rows AFTER the subsection swept too — otherwise this gate can only
    ever report a subset of its own denominator as clean.
    """
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n"
        "## Hard gates\n\n"
        "| # | Gate | Enforcer |\n"
        "|---|---|---|\n"
        "| G1 | Before the subsection | `first.py` |\n\n"
        "### Why the second gate exists\n\n"
        "| G2 | After the subsection, still a gate | `second.py` |\n\n"
        "## Anti-patterns\n\n"
        "- Not a gate at all.\n"
    ))
    _with_script(root, "scripts/first.py")
    _with_script(root, "scripts/second.py")

    report = check_gate_mechanisms(root)

    assert report.total_gates >= 2, "the subsection truncated the section again"
    assert report.findings == []


def test_a_table_row_inherits_a_mechanism_named_in_its_section_prose(tmp_path: Path) -> None:
    """A verdict table specifies a mechanism the section already named.

    `cycle-implement.md § Hard gates (per phase boundary)` names `mini_review.py`
    in prose and then tabulates `PHASE_REVIEW_PASS` / `PHASE_REVIEW_NEEDS_FIX`.
    Those rows are that script's output contract, not two further gates with
    two further enforcers. Demanding a citation per row would push someone to
    paste the same filename twice for tidiness, which teaches nothing.
    """
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates (phase boundary)\n\n"
        "When a commit closes a phase, `mini_review.py` MUST run. Verdict drives:\n\n"
        "| Verdict | Action |\n"
        "|---|---|\n"
        "| `PASS` | Proceed |\n"
        "| `NEEDS_FIX` | Halt |\n"
    ))
    _with_script(root, "skills/implement/scripts/mini_review.py")

    report = check_gate_mechanisms(root)

    assert report.findings == []
    assert report.total_gates == 2


def test_a_bullet_does_not_inherit_from_section_prose(tmp_path: Path) -> None:
    """Inheritance is for tables only.

    A bullet is an autonomous gate: five bullets under one paragraph that
    happens to mention a script are five different claims, and letting them all
    borrow that one citation is how the 82% got there in the first place.
    """
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "The loop runs `mini_review.py` at each boundary.\n\n"
        "- Test suite green before commit.\n"
        "- Linter clean.\n"
    ))
    _with_script(root, "skills/implement/scripts/mini_review.py")

    findings = check_gate_mechanisms(root).findings

    assert len(findings) == 2
    assert {f.kind for f in findings} == {"gate_without_mechanism"}


def test_a_table_inherits_an_exemption_declared_in_its_section_prose(tmp_path: Path) -> None:
    """One note above the table beats the same marker pasted into six rows.

    `cycle-trajectory-review.md` was the real case: measured 2026-08-27, `skills/trajectory-review/`
    shipped a SKILL.md and no scripts, so all six of its hard caps were asserted
    rather than computed. The rule and its skill were retired on 2026-08-31 for
    exactly that reason; the pattern they demonstrated is why this test exists. That is one fact about the slice, and stating it once
    where the reader meets the table says more than six identical parentheticals
    — which would read as six independent decisions.
    """
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "> **None of the caps below is computed.** The slice ships no scripts. "
        "_(not mechanized: no script in this repository emits this verdict)_\n\n"
        "| Cap | Trigger |\n"
        "|---|---|\n"
        "| Golden rule missing | not found |\n"
        "| Config not enabled | missing |\n"
    ))

    report = check_gate_mechanisms(root)

    assert report.findings == []
    assert report.unmechanized == 2
    assert report.named == 0


def test_a_bullet_does_not_inherit_an_exemption_either(tmp_path: Path) -> None:
    """Inheritance stays table-only in both directions.

    Letting bullets borrow a section-level exemption would hand every rule a
    one-line way to exempt its whole gate list, which is the escape hatch this
    check exists to close.
    """
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "Nothing here runs. _(not mechanized: the slice ships no scripts)_\n\n"
        "- Test suite green before commit.\n"
    ))

    findings = check_gate_mechanisms(root).findings

    assert len(findings) == 1
    assert findings[0].kind == "gate_without_mechanism"


def test_a_bullet_carries_its_continuation_lines(tmp_path: Path) -> None:
    """A gate is the whole bullet, not its first physical line.

    Found by the check reporting three `cycle-review.md` gates that had just
    been annotated: the mechanism had landed on the wrapped line, and a parser
    that reads only the first line of a bullet cannot see it. A checker that
    fails on correct input is the false positive this ecosystem treats as worse
    than no checker.
    """
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "- New secrets committed (any pattern matching `.env`, `credentials*`,\n"
        "  `*.pem`, `*.key`) — `stop-validation.py`.\n"
        "- Another gate — `validate-command.py`.\n"
    ))
    _with_script(root, "hooks/stop-validation.py")
    _with_script(root, "hooks/validate-command.py")

    report = check_gate_mechanisms(root)

    assert report.findings == []
    assert report.total_gates == 2, "a wrapped bullet is one gate, not two"


def test_a_table_row_carries_its_continuation_lines(tmp_path: Path) -> None:
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "| # | Gate |\n|---|---|\n"
        "| G1 | Routes —\n"
        "  `route_domain.py` refuses the repo. |\n"
    ))
    _with_script(root, "mechanisms/cycle/route_domain.py")

    report = check_gate_mechanisms(root)

    assert report.findings == []
    assert report.total_gates == 1


def test_a_citation_may_carry_the_invocation_not_only_the_filename(tmp_path: Path) -> None:
    """`` `flip_milestone_checkbox.py --commit` `` names the mechanism better.

    Which flags a gate depends on is part of what enforces it: the flip is only
    atomic under `--commit`. Rejecting the fuller citation would push the author
    to write the poorer one to satisfy the checker.
    """
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "- No silent flip — `flip_milestone_checkbox.py --commit`, which aborts "
        "when the commit fails.\n"
    ))
    _with_script(root, "skills/release/scripts/flip_milestone_checkbox.py")

    report = check_gate_mechanisms(root)

    assert report.findings == []
    assert report.named == 1


def test_a_partially_mechanized_gate_is_counted_apart(tmp_path: Path) -> None:
    """A gate that names a script AND declares a residue is neither category.

    `cycle-acceptance`'s flip gate is the real case: `check_goal_met.py` refuses
    to release the session on a bad verdict, while the flip itself never reads
    one. Filing that as fully named would overstate the coverage this movement
    is measuring.
    """
    root = _rules(tmp_path, "cycle-demo.md", (
        "# Demo\n\n## Hard gates\n\n"
        "- No flip without a green verdict — enforced after the fact by "
        "`check_goal_met.py` _(not mechanized at the point of action: debt since "
        "2026-08-27 — the flip script never reads the verdict)_\n"
    ))
    _with_script(root, "skills/session-goal/scripts/check_goal_met.py")

    report = check_gate_mechanisms(root)

    assert report.findings == []
    assert report.partial == 1
    assert report.named == 0
    assert report.unmechanized == 0


# ---------------------------------------------------------------------------
# The gate over this repository
# ---------------------------------------------------------------------------

def test_this_repository_has_every_gate_mechanism_named() -> None:
    """The check turned on its own repository.

    Left failing while the 50 measured gates are annotated would make the suite
    red for work in progress; it is written last and must pass once movement 1
    lands.
    """
    report = check_gate_mechanisms(REPO_ROOT)

    assert report.total_gates > 0, "the sweep found no gate at all — parser broken"
    assert report.findings == [], "\n".join(
        f"{f.rule}: [{f.kind}] {f.gate}" for f in report.findings
    )


def test_the_cli_exits_nonzero_on_a_finding(tmp_path: Path) -> None:
    import subprocess

    _rules(tmp_path, "cycle-demo.md", "# Demo\n\n## Hard gates\n\n- Nothing named.\n")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "mechanisms" / "gates" / "check_gate_mechanisms.py"),
         "--repo-root", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 1
    assert "gate_without_mechanism" in result.stdout


@pytest.mark.parametrize("verb", ["--strict", ""])
def test_the_cli_reports_the_count_it_swept(tmp_path: Path, verb: str) -> None:
    """A checker that says PASS without saying how much it looked at is the
    empty-gate shape this ecosystem refuses everywhere else."""
    import subprocess

    root = _rules(tmp_path, "cycle-demo.md", "# Demo\n\n## Hard gates\n\n- Fine — `x.py`.\n")
    _with_script(root, "scripts/x.py")
    argv = [sys.executable, str(REPO_ROOT / "mechanisms" / "gates" / "check_gate_mechanisms.py"),
            "--repo-root", str(tmp_path)]
    if verb:
        argv.append(verb)

    result = subprocess.run(argv, capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert "1 gate" in result.stdout


# ===========================================================================
# EXEMPTION CLASSES — added 2026-09-08
#
# `0 unresolved` proved every gate either names a mechanism or carries a reason.
# What the report could not say is WHICH KIND of reason, and the seventeen
# exemptions turned out to hold three unrelated claims:
#
#   judgement   automating it would produce verdicts about LANGUAGE, not about
#               the work. Permanent by decision, and measured: four of them were
#               pressure-tested across model tiers on 2026-08-28 — redundant on
#               Opus, and one caught a fabricated justification on Haiku
#               (`.squad/wiki/references/judgement-gates-are-insurance.md`).
#   debt        it is missing, and the line says what is missing.
#   regression  a mechanism EXISTED and was withdrawn. This is lost coverage, not
#               debt that was never paid, and reading it as debt hides that the
#               kit used to be stricter here.
#   external    a third-party plugin enforces it; this kit can state the wiring
#               and cannot verify it.
#
# Summing them into one number says "17 gates are not mechanized", which invites
# the wrong conclusion in both directions: that the kit has 17 holes, or that
# 17 deliberate decisions are all equally fine.
#
# `debt` and `regression` also carry a date, so the report can age them. It does
# NOT fail on age by default — how long a debt may live is the operator's call,
# not the kit's — but `--max-debt-age` makes it enforceable for a project that
# wants a ceiling.
# ===========================================================================

def test_the_kit_declares_a_class_on_every_exemption() -> None:
    """The regression. Every exemption in the shipped rules names its class."""
    report = check_gate_mechanisms(REPO_ROOT)

    assert not [f for f in report.findings if f.kind == "exemption_without_class"], [
        (f.rule, f.gate) for f in report.findings if f.kind == "exemption_without_class"
    ]


def test_the_report_separates_the_classes() -> None:
    """A single 'not mechanized' count is the thing this replaces."""
    report = check_gate_mechanisms(REPO_ROOT)

    assert set(report.by_class) <= {"judgement", "debt", "regression", "external", "composed"}
    assert sum(report.by_class.values()) == report.unmechanized + report.partial
    # The kit does have judgement gates, and it does have declared debt. If either
    # became zero, this test should be read again rather than deleted.
    assert report.by_class.get("judgement", 0) > 0

    # `composed` is not a hole: the release LOCKED gate reads verdicts the chain
    # already emitted. Counting it as debt would report an enforced gate as missing.
    assert report.by_class.get("composed", 0) > 0


def test_an_exemption_without_a_class_is_a_finding(tmp_path: Path) -> None:
    root = _rules(tmp_path, "cycle-example.md", """
## Hard gates

- **Something** — _(not mechanized: nobody got to it yet)_
""")
    report = check_gate_mechanisms(root)

    kinds = [f.kind for f in report.findings]
    assert "exemption_without_class" in kinds, kinds


def test_debt_must_carry_a_date_and_regression_too(tmp_path: Path) -> None:
    """Without a date, an ageing report cannot age anything.

    `judgement` and `external` are exempt from this: neither is expected to end,
    so a date on them would be decoration that goes stale.
    """
    root = _rules(tmp_path, "cycle-example.md", """
## Hard gates

- **A** — _(not mechanized: debt — no script confronts the list)_
- **B** — _(not mechanized: regression — a retired skill used to do it)_
- **C** — _(not mechanized: judgement — a regex would grade language)_
""")
    report = check_gate_mechanisms(root)

    dated = [f for f in report.findings if f.kind == "undated_exemption"]
    assert len(dated) == 2, [f.gate for f in dated]
    assert all("judgement" not in f.gate for f in dated)


def test_a_dated_debt_passes_and_reports_its_age(tmp_path: Path) -> None:
    root = _rules(tmp_path, "cycle-example.md", """
## Hard gates

- **A** — _(not mechanized: debt since 2026-01-15 — no script confronts the list)_
""")
    report = check_gate_mechanisms(root)

    assert not [f for f in report.findings if f.kind in ("undated_exemption", "exemption_without_class")]
    assert report.by_class.get("debt") == 1
    assert report.oldest_debt == "2026-01-15"


def test_max_debt_age_is_opt_in(tmp_path: Path) -> None:
    """How long a debt may live is the operator's call.

    The kit reports the age always and refuses only when a project sets a ceiling —
    a gate that failed on age by default would fire on every consumer that has not
    decided what its ceiling is.
    """
    root = _rules(tmp_path, "cycle-example.md", """
## Hard gates

- **A** — _(not mechanized: debt since 2020-01-01 — ancient)_
""")

    assert not [f for f in check_gate_mechanisms(root).findings if f.kind == "debt_too_old"]

    aged = check_gate_mechanisms(root, max_debt_age_days=30)
    assert [f for f in aged.findings if f.kind == "debt_too_old"]


# ------------------------------------------------------------------ #77


def test_a_gate_section_under_any_heading_is_swept(tmp_path) -> None:
    """#77. `_SECTION_RE` required the literal `Hard gate`, so `## Gates` and
    `## Confidence gates between phases` fell through `if not sections: continue` —
    neither swept nor reported.

    Measured 2026-09-11: 14 cycle rules on disk, 9 swept, `0 unresolved` claimed over a
    population that excluded two rules holding 16 gates between them. Widening the match
    surfaced 7 real findings that had been invisible.
    """
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "cycle-x.md").write_text(
        "# X\n\n## Gates\n\n| Gate | What | By |\n|---|---|---|\n"
        "| G-1 | something | `check_x.py` |\n", encoding="utf-8")

    report = check_gate_mechanisms(tmp_path)

    assert report.rules_swept == 1, "a section headed `## Gates` must be swept"


def test_a_rule_with_no_gate_section_is_named_not_dropped(tmp_path) -> None:
    """Absent must not read as clean. `check_prose_write_paths.py` sets the precedent:
    print what was swept so CLEAN can never mean "nothing read"."""
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "cycle-quiet.md").write_text("# Quiet\n\n## Purpose\n\nNo gates here.\n",
                                          encoding="utf-8")

    report = check_gate_mechanisms(tmp_path)

    assert report.rules_without_gates == ["cycle-quiet.md"]
    assert report.rules_swept == 0


def test_the_schema_is_not_counted_as_a_rule_that_lost_its_gates(tmp_path) -> None:
    """`cycle-rule-schema.md` is what every cycle rule is written AGAINST. Listing it
    as a rule with no gate section reports a fact about a document that was never
    supposed to have any."""
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "cycle-rule-schema.md").write_text("# Schema\n\n## Purpose\n\nx\n",
                                                encoding="utf-8")

    report = check_gate_mechanisms(tmp_path)

    assert report.rules_without_gates == []
    assert report.rules_swept == 0


def test_this_repository_sweeps_every_cycle_rule_it_has() -> None:
    """The population and the directory must agree, or `0 unresolved` means something
    narrower than a reader takes it to mean."""
    repo = Path(__file__).resolve().parents[1]
    on_disk = {p.name for p in (repo / "rules").glob("cycle-*.md")} - {"cycle-rule-schema.md"}

    report = check_gate_mechanisms(repo)

    assert report.rules_swept + len(report.rules_without_gates) == len(on_disk), (
        f"swept {report.rules_swept} + {len(report.rules_without_gates)} without gates, "
        f"but {len(on_disk)} cycle rules are on disk")
