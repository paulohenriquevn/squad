"""A refusal that hides the list sends its reader to the gate's source.

Measured over a 20-hour consumer session, 676 Bash commands: **64 of them — 9% — were
the agent reading a gate's `.py` with grep or sed to discover what shape the gate
wanted.** They cluster in four skills: `brainstorm-pieces` (11), `plan-confidence` (11),
`discover-confidence` (10), `plan-alignment` (10).

The loop is always the same. Run the gate, get refused, open the source, adjust, run
again:

    16:59:12  grep -nE "^ACCEPTABLE" -A 22 ...py    ← after a refusal that truncated the list
    17:03:46  grep -n "NODE_KINDS" ...py            ← after one that did not print it
    16:57:48  grep -nE "def _count|ENTRY|bullet"    ← after one that named no format at all

These gates are HONEST — each names what failed. They are not ACTIONABLE, which is a
different property: a reader cannot tell from the refusal what would pass. Where the
gate holds the answer as a constant, printing it costs one f-string and removes the
whole detour.

The rule this file fixes: **when a gate refuses because a value is outside a closed
vocabulary, or because items from a fixed list are absent, the refusal names the whole
list.** Not the first three. Not a truncated parenthetical.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _sections_of(module: Path, name: str) -> list:
    import importlib.util
    spec = importlib.util.spec_from_file_location("_probe", module)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_probe"] = mod
    spec.loader.exec_module(mod)
    return list(getattr(mod, name))


def test_a_missing_section_refusal_lists_every_missing_one(tmp_path: Path) -> None:
    """`missing[:3]` told a reader three of N and nothing about the rest, so the next
    run surfaced the next three. The document is fixed once when the list is whole."""
    script = _ROOT / "skills" / "discover-confidence" / "scripts" / "check_opportunity_completeness.py"
    mandatory = _sections_of(script, "MANDATORY_SECTIONS")
    assert len(mandatory) > 3, "this test is meaningless if the list fits in the old cap"

    doc = tmp_path / "x-opportunity.md"
    doc.write_text("# An opportunity with nothing in it\n", encoding="utf-8")

    # Called directly: this is a MODULE, not an executable. Running it by subprocess
    # exits 0 with no output, which would have made this test pass on nothing.
    import importlib.util
    spec = importlib.util.spec_from_file_location("_oc", script)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_oc"] = mod
    spec.loader.exec_module(mod)
    report = mod.check_opportunity_completeness(doc)
    out = " | ".join(report.get("detractors", []))

    named = [n for n, _ in mandatory if n.lower() in out.lower()]
    assert len(named) == len(mandatory), (
        f"the refusal named {len(named)} of {len(mandatory)} missing sections. "
        f"A reader fixes three, re-runs, and meets the next three:\n{out[:600]}")


def test_the_concurrency_refusal_lists_every_accepted_signal() -> None:
    """The refusal must RENDER the list that decides, whole, rather than freeze a parenthetical.

    Its yardstick was `CONCURRENCY_SIGNALS` until 2026-09-23 — and that is the list which
    DETECTS whether a task involves concurrency (`mutex`, `SharedArrayBuffer`), not the one
    which ACCEPTS a subsection (`go test -race`, `loom::`). So this test required the message
    to be long and derived from the wrong constant, and passed while a reader who copied a
    printed token failed again (#175).

    The purpose was right: a frozen parenthetical naming six while the matcher held more is
    how a message drifts from the code. The measure was wrong, and it is now the deciding
    list plus its escape, because there are two ways to pass and a message naming one hides
    the other.

    Third test this day found encoding the defect it was written near — see
    `test_blocks_out_of_sequence_are_not_a_finding` and
    `test_a_reused_id_is_refused_and_mere_sequence_is_not` (#169). Corrected rather than
    deleted: deleting it would remove the only guard against the parenthetical coming back.
    """
    script = _ROOT / "skills" / "plan-confidence" / "scripts" / "check_concurrency_tests.py"
    source = script.read_text(encoding="utf-8")

    refusal = [ln for ln in source.splitlines() if "does not contain an acceptable" in ln]
    assert refusal, "the refusal moved; this test needs re-pointing"

    window = source[source.index(refusal[0]):][:800]
    assert "_accepted_signals()" in window, (
        "the refusal spells its accepted signals as a frozen parenthetical instead of "
        "rendering the list the module actually matches against — so the two drift, and "
        "the reader greps for the real one")

    # And the rendering must be DERIVED, or it is the same frozen literal with extra steps.
    import importlib.util
    spec = importlib.util.spec_from_file_location("_cc", script)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_cc"] = mod
    spec.loader.exec_module(mod)
    rendered = mod._accepted_signals()
    tokens = [t.strip() for t in rendered.split(" · ") if t.strip()]
    deciding = len(mod.RACE_TEST_SIGNALS) + len(mod.ESCAPE_MARKERS)
    assert len(tokens) == deciding, (
        f"the message renders {len(tokens)} token(s) and the decider consults {deciding}. "
        f"Whole, or a reader fixes what it named and meets what it did not:\n{rendered}")
    # And derived, not a literal that happens to be the same length today.
    assert "RACE_TEST_SIGNALS" in source and "_accepted_signals" in source


def test_the_scenario_class_refusal_names_the_four() -> None:
    """A flow tagged with a class outside the set is refused; the set is four names
    long and lives one constant away."""
    script = _ROOT / "skills" / "plan-alignment" / "scripts" / "score_alignment.py"
    source = script.read_text(encoding="utf-8")

    assert '_SCENARIO_CLASSES' in source
    # Where the score reports the gap, the four names must reach the output.
    idx = source.index("_SCENARIO_CLASSES = ")
    uses = source.count("_SCENARIO_CLASSES")
    assert uses >= 3, "the constant is defined and barely used; the report likely hardcodes"
    reported = any(
        "_SCENARIO_CLASSES" in ln and ("join" in ln or "f\"" in ln or "f'" in ln)
        for ln in source[idx:].splitlines())
    assert reported, (
        "no line renders `_SCENARIO_CLASSES` into a message — a flow tagged wrongly is "
        "told it is wrong and not which four tags exist")
