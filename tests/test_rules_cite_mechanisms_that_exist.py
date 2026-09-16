"""A rule that names a script as enforcement must name one that ships.

`rules/records-location.md` had an "Enforcement" section listing three mechanisms.
Measured 2026-09-05: one holds, one was deleted with the skill it belonged to
(`install_goal_hook.py`, gone in `77501b0`), and one never existed at all — the
finding `split_knowledge_base` appeared in that file and nowhere else in the
repository.

Two of three, in a section whose whole job is to tell a reader the constraint is
enforced. That is worse than listing none: a reader who is told a gate exists stops
looking for the gap.

The shape is the one this repository keeps finding, arriving through documentation
instead of code — a deletion that trimmed the implementation and left the prose. The
README described three advisory skills that had been deleted; a gate's doc promised a
floor the code had lost; a consumer's rules named a hook that was not on the machine.
Rules are read by agents and acted on, which is why this sweep exists at the rules
layer rather than in one file's own test.

Deliberately narrow. It checks references that READ as a script — a name ending in
`.py` or `.sh` inside backticks — and only in `rules/`, where the text is an
instruction rather than history or illustration. `CHANGELOG.md` legitimately names
deleted scripts; a template legitimately writes `bar.py` as an example.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_REF = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|sh))`")

#: Names a rule may cite without the kit shipping them. Each needs a reason — an
#: exemption nobody probes is a door.
EXEMPT = {
    # Written INTO a consumer by a skill, so the kit never holds one.
    "check_quality.py", "smell_checks.py", "smell_python.py", "smell_types.py",
    # A consumer-side path, named as a destination rather than a kit file.
    ".claude/hooks/check_quality.py",
}


#: Words that turn a mention into a record of absence. Deliberately explicit rather
#: than a general negation check: "not refused" would match a vague hedge, and a
#: hedge is how a live claim survives a sweep.
ABSENCE = (
    "GONE", "NEVER EXISTED", "WAS DELETED", "DELETED IN", "DOES NOT EXIST",
    "NO LONGER", "NOTHING ENFORCES", "SHIPS NOWHERE",
)


def _marks_absence(line: str, ref_at: int) -> bool:
    """Does this line announce the absence BEFORE naming the script?

    Order is the whole check, and mutation is what showed why. A line-wide search
    let a live claim survive as long as the same sentence mentioned a deletion
    somewhere later — which is exactly the shape of the correction this test was
    written for, and therefore exactly the shape a regression would take. Announcing
    it first is what a reader actually needs: they must know the mechanism is gone
    before they read its name, or they have already believed it.
    """
    upper = line.upper()
    return any(0 <= upper.find(word) < ref_at for word in ABSENCE)


def _tracked() -> set[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return set(out.split())


def _resolves(ref: str, doc: Path, tracked: set[str], names: set[str]) -> bool:
    if ref in EXEMPT or ref in tracked or (ROOT / ref).exists():
        return True
    if (doc.parent / ref).exists():
        return True
    return Path(ref).name in names


@pytest.mark.parametrize("rule", sorted((ROOT / "rules").glob("*.md")),
                         ids=lambda p: p.name)
def test_a_rule_does_not_name_a_script_the_kit_does_not_ship(rule: Path) -> None:
    tracked = _tracked()
    names = {Path(f).name for f in tracked}

    missing: list[str] = []
    for line in rule.read_text(encoding="utf-8").splitlines():
        # A line that MARKS the reference as absent is the correction, not the
        # claim. Recording that a mechanism was deleted is the most useful thing a
        # rule can say about it, and a sweep that forbade naming it would push the
        # next reader back to believing the gate exists. Struck-through text counts,
        # and so does prose that says so in words.
        if line.count("~~") >= 2:
            continue
        for match in SCRIPT_REF.finditer(line):
            ref = match.group(1)
            if _marks_absence(line, match.start()):
                continue
            if not _resolves(ref, rule, tracked, names):
                missing.append(f"{ref} (line: {line.strip()[:70]})")

    assert not missing, (
        f"{rule.relative_to(ROOT)} names script(s) that ship nowhere: {missing}. "
        f"A rule is read as instruction — naming a gate that does not exist tells "
        f"the reader the constraint is enforced and stops them looking."
    )


def test_the_sweep_would_notice_the_defect_it_was_written_for() -> None:
    """The sweep's own oracle, so it cannot pass by matching nothing.

    Without this, deleting the regex or narrowing the glob leaves every parametrised
    case green and the file reads as a working guard.
    """
    tracked = _tracked()
    names = {Path(f).name for f in tracked}
    rule = ROOT / "rules" / "records-location.md"

    assert not _resolves("install_goal_hook.py", rule, tracked, names), (
        "install_goal_hook.py is back — this test's premise is stale and the "
        "correction written into records-location.md needs revisiting"
    )
    assert SCRIPT_REF.findall("- `install_goal_hook.py` refuses paths") == [
        "install_goal_hook.py"
    ], "the reference pattern no longer matches the shape it was written for"


def test_the_absence_marker_does_not_swallow_a_live_claim() -> None:
    """The exemption is a door, so it gets probed.

    A line may name a missing script only while SAYING it is missing. The sentence
    that motivated this exemption is the rule's own correction; the sentence it must
    never excuse is the one that was there before it.
    """
    announced = "Nothing enforces this today. `install_goal_hook.py` did — it refused"
    assert _marks_absence(announced, announced.index("`install_goal_hook.py`"))

    live = "`install_goal_hook.py` enforces this: a `--roadmap` outside the root is refused."
    assert not _marks_absence(live, live.index("`install_goal_hook.py`")), (
        "the original claim would pass the exemption, which would make this whole "
        "sweep decorative"
    )

    # The shape mutation found: a live claim in a line that mentions a deletion
    # LATER. Searching the whole line excused it, because the correction this test
    # was written for happens to be one sentence carrying both.
    trailing = ("`install_goal_hook.py` enforces this — and it was deleted in `77501b0` "
                "with the skill it belonged to.")
    assert not _marks_absence(trailing, trailing.index("`install_goal_hook.py`")), (
        "a deletion mentioned after the claim does not un-make the claim; the reader "
        "has already read it as live"
    )


def test_no_procedure_concludes_a_project_phase_from_a_missing_file() -> None:
    """"pre-code phase" is a claim about the repository; a missing manifest is a fact
    about the manifest. The gates stopped confusing them on 2026-09-15 and the procedures
    that invoke those gates kept prescribing it — eight occurrences across four files,
    after the code was fixed.

    That is the gap a consumer session named: a fix that lands in code and not in what
    invokes it is half a fix, and the missing half is the one a new reader follows.

    Two uses survive and both are legitimate: a section describing a project that
    genuinely has no source yet, and the comment that quotes the retired phrase to explain
    why it went. A phrase used to DESCRIBE a real state is not the defect; a phrase used
    to CONCLUDE one from an absent file is.
    """
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for doc in list(root.glob("skills/**/*.md")) + list(root.glob("rules/*.md")):
        if "/tests/" in str(doc):
            continue
        for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if "pre-code phase" not in line:
                continue
            # The offence is concluding the phase from ONE ecosystem's manifest. Saying
            # a repo with NO manifest of any language is pre-code is not that — it is the
            # honest reading, and `cycle-implement.md` already writes it as "genuine".
            #
            # This exemption started narrower and refused three correct lines in
            # `rules/`, which is the same shape as the pre-filter that cost a consumer
            # session a wrong count an hour earlier: a guard that decides in advance what
            # is worth examining fails silently toward MORE findings here, and toward
            # fewer there. Both are the guard deciding instead of measuring.
            if re.search(r"reality check|without source code|NOT \"pre-code"
                         r"|no language manifest at all|genuine pre-code"
                         r"|no source code exists|not installed", line, re.I):
                continue
            offenders.append(f"{doc.relative_to(root)}:{number}")
    assert not offenders, (
        f"these conclude a project phase from an absent file: {offenders}. Say what was "
        f"looked for and not found.")


def test_no_procedure_names_npm_as_the_only_suite() -> None:
    """The validation gate runs Go, Rust, Python and npm. A checklist naming only `npm
    test` read a Go workspace with 1918 lines of new code as having nothing to run."""
    root = Path(__file__).resolve().parents[1]
    template = (root / "skills" / "implement" / "templates"
                / "implementation-task-template.md").read_text(encoding="utf-8")
    for other in ("go test", "cargo", "pytest"):
        assert other in template, f"the task checklist does not mention {other}"
