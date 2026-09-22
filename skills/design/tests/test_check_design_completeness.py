"""The drawings that force the decisions a product cannot retrofit.

Four of the five are mandatory because each answers a question that is cheap now and
expensive later: what the central object's lifecycle is, where untrusted code stops,
what the real call order is when things fail, and what survives a process death. The
fifth is derived — a component map drawn FIRST is decoration, because it looks like
design happened and forces no choice.

The tests that matter are the ones about what the gate REFUSES to conclude: it counts
drawings and cross-references pieces, and cannot say a state machine has the right
states.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_design_completeness import (  # noqa: E402 — post-bootstrap import
    DRAWINGS,
    EXIT,
    MIN_MERMAID_LINES,
    NOT_CHECKED,
    Report,
    check,
    declares_kind,
    mermaid_blocks,
    render,
    verdict_of,
)

GOOD = {
    "states.md": """# D1
```mermaid
stateDiagram-v2
    [*] --> submitted
    submitted --> running
    running --> terminated
```
""",
    "trust.md": """# D2
```mermaid
flowchart LR
    agent[user code] -->|scoped token| api[control]
    api --> store[(state)]
```
""",
    "sequence.md": """# D3
```mermaid
sequenceDiagram
    U->>A: push
    A->>B: build
    B--xA: failed
```
""",
    "durability.md": """# D4
```mermaid
flowchart TB
    agent -->|checkpoint 30s| store
    store -->|restore| agent
```
""",
    "system-map.md": """# D5
```mermaid
flowchart TB
    api[PIECE-1 control]
    rt[PIECE-2 runtime]
    api --> rt
```
""",
}

SIGNOFF = """# Sign-off

## Sign-off

- [ ] The lifecycle is the real one
"""


def _project(tmp_path: Path, *, files: dict | None = None, pieces: str = "",
             signoff: str = "") -> Path:
    design = tmp_path / ".squad" / "wiki" / "design"
    design.mkdir(parents=True)
    for name, body in (GOOD if files is None else files).items():
        (design / name).write_text(body, encoding="utf-8")
    if signoff:
        (design / "sign-off.md").write_text(signoff, encoding="utf-8")
    product = tmp_path / ".squad" / "wiki" / "product"
    product.mkdir(parents=True)
    (product / "technical-pieces.md").write_text(
        pieces or "# Pieces\n\n## PIECE-1 — Control\n\n## PIECE-2 — Runtime\n",
        encoding="utf-8")
    return tmp_path


# ------------------------------------------------------------------ the four decisions


def test_four_drawings_are_mandatory_and_the_map_is_derived() -> None:
    """D5 drawn first is decoration: it looks like design happened and decides nothing.
    The four above it each force a decision that cannot be retrofitted."""
    mandatory = {d.key for d in DRAWINGS if d.mandatory}
    derived = {d.key for d in DRAWINGS if not d.mandatory}

    assert mandatory == {"states", "trust", "sequence", "durability"}
    assert derived == {"system-map"}


def test_a_missing_mandatory_drawing_is_structural(tmp_path: Path) -> None:
    """No editing of the other four supplies the decision this one was to make."""
    files = {k: v for k, v in GOOD.items() if k != "trust.md"}

    rep = check(_project(tmp_path, files=files))

    assert rep.verdict == "INVALID"
    assert [f.code for f in rep.findings] == ["drawing_missing"]
    assert "trust" in rep.missing


def test_prose_about_a_diagram_is_not_a_diagram(tmp_path: Path) -> None:
    files = dict(GOOD, **{"states.md": "# D1\n\nThe agent has a lifecycle. It is complex.\n"})

    rep = check(_project(tmp_path, files=files))

    assert "drawing_has_no_mermaid" in [f.code for f in rep.findings]


def test_a_diagram_in_the_wrong_slot_is_reported(tmp_path: Path) -> None:
    """A sequence diagram filed as the state machine answers a different question than
    the slot exists for."""
    files = dict(GOOD, **{"states.md": GOOD["sequence.md"]})

    rep = check(_project(tmp_path, files=files))

    assert "wrong_diagram_kind" in [f.code for f in rep.findings]


def test_a_placeholder_is_worse_than_an_absent_drawing(tmp_path: Path) -> None:
    """An open question drawn as if settled does not report itself; an absent drawing
    does."""
    files = dict(GOOD, **{"trust.md": GOOD["trust.md"] + "\nEgress policy: TBD\n"})

    rep = check(_project(tmp_path, files=files))

    assert "placeholder_in_drawing" in [f.code for f in rep.findings]


# ------------------------------------------------------------------ the stub floor


def test_two_labelled_edges_are_not_a_stub(tmp_path: Path) -> None:
    """The floor was 4 and it was wrong. A durability drawing of three lines carrying
    two LABELLED edges answers its slot's question exactly, and a check that flags it
    teaches people to pad diagrams to clear a counter."""
    assert MIN_MERMAID_LINES == 3

    rep = check(_project(tmp_path))

    assert "drawing_is_a_stub" not in [f.code for f in rep.findings]


def test_a_kind_line_and_one_edge_is_a_stub(tmp_path: Path) -> None:
    files = dict(GOOD, **{"trust.md": "# D2\n```mermaid\nflowchart LR\n    A --> B\n```\n"})

    rep = check(_project(tmp_path, files=files))

    assert "drawing_is_a_stub" in [f.code for f in rep.findings]


# ------------------------------------------------------------------ coverage


def test_a_piece_with_no_place_in_the_map_is_reported(tmp_path: Path) -> None:
    """Either it has no place in the system as drawn, or the map is missing a
    component. Both are answers worth having before an item is filed against it."""
    rep = check(_project(tmp_path,
                         pieces="# P\n\n## PIECE-1 — Control\n\n## PIECE-9 — Metering\n"))

    assert rep.uncovered == ["PIECE-9"]
    assert "piece_not_in_map" in [f.code for f in rep.findings]


def test_unreadable_pieces_means_coverage_was_not_checked(tmp_path: Path) -> None:
    """NOT that it passed. The drawings may omit half the product."""
    design = tmp_path / ".squad" / "wiki" / "design"
    design.mkdir(parents=True)
    for name, body in GOOD.items():
        (design / name).write_text(body, encoding="utf-8")

    rep = check(tmp_path)

    finding = next(f for f in rep.findings if f.code == "pieces_unreadable")
    assert "NOT checked" in finding.detail


# ------------------------------------------------------------------ the signature


def test_a_complete_covered_set_nobody_signed_is_not_agreed(tmp_path: Path) -> None:
    rep = check(_project(tmp_path, signoff=SIGNOFF))

    assert rep.verdict == "AWAITING_REVIEW"


def test_a_judge_may_not_sign_this_gate(tmp_path: Path) -> None:
    """Same argument as G-B5: a judge scoring a system design grades it against the
    document that declares it."""
    signed = SIGNOFF.replace("- [ ]", "- [x]") + "\n<!-- signed-by: judge/x -->\n"

    rep = check(_project(tmp_path, signoff=signed))

    assert rep.verdict == "AWAITING_REVIEW"


def test_a_human_signature_closes_it(tmp_path: Path) -> None:
    signed = SIGNOFF.replace("- [ ]", "- [x]") + "\n<!-- signed-by: human/paulo -->\n"

    rep = check(_project(tmp_path, signoff=signed))

    assert rep.verdict == "DESIGN_AGREED"


def test_a_signature_does_not_override_an_uncovered_piece(tmp_path: Path) -> None:
    """Signing to unblock the backlog must not work."""
    signed = SIGNOFF.replace("- [ ]", "- [x]") + "\n<!-- signed-by: human/paulo -->\n"

    rep = check(_project(tmp_path, pieces="# P\n\n## PIECE-9 — Orphan\n", signoff=signed))

    assert rep.verdict == "NEEDS_REVISION"


# ------------------------------------------------------------------ honesty


def test_no_design_directory_is_not_a_pass(tmp_path: Path) -> None:
    rep = check(tmp_path)

    assert rep.verdict == "INVALID"
    assert "nothing was assessed" in rep.unmeasured_because


def test_the_gate_states_what_it_cannot_judge() -> None:
    """It counts and cross-references. Whether a state machine has the RIGHT states is
    not a countable property, which is why the signature must be a person's."""
    joined = " ".join(NOT_CHECKED)

    assert "CORRECT" in joined
    assert "trust boundary is in the right place" in joined


def test_every_verdict_token_is_declared_in_the_bands_registry() -> None:
    bands = Path(__file__).resolve().parents[3] / "rules" / "verdict-bands.txt"
    declared = {line.split("|")[0].strip()
                for line in bands.read_text(encoding="utf-8").splitlines()
                if "|" in line and not line.lstrip().startswith("#")}

    assert set(EXIT) <= declared, set(EXIT) - declared


@pytest.mark.parametrize("severities,expected", [
    ([], "AWAITING_REVIEW"),
    (["major"], "NEEDS_REVISION"),
    (["blocker"], "INVALID"),
])
def test_the_verdict_is_derived_from_the_worst_finding(severities, expected) -> None:
    from check_design_completeness import Finding

    rep = Report(findings=[Finding("c", s, "x", "d") for s in severities])

    assert verdict_of(rep) == expected


# ------------------------------------------------------------------ helpers


def test_mermaid_extraction_and_kind_detection() -> None:
    blocks = mermaid_blocks(GOOD["states.md"])

    assert len(blocks) == 1
    assert declares_kind(blocks[0], ("stateDiagram-v2",))
    assert not declares_kind(blocks[0], ("sequenceDiagram",))


# ------------------------------------------------------------------ the render path


def test_the_gate_never_requires_a_rendered_file(tmp_path: Path) -> None:
    """Rendering is for a review session; the mermaid is the drawing.

    The first version of `SKILL.md` pointed step 4 at `build_walkthrough.py`, which
    takes a declarative YAML spec of ONE ITEM's flows — a different input and a
    different artifact. It would have failed on the first run. `diagram-design` accepts
    Markdown carrying fenced mermaid blocks, which is exactly the shape of these files,
    and it is a separate install: a phase that depended on it would stop for a plugin
    nobody asked the project to have.
    """
    rep = check(_project(tmp_path))

    assert rep.verdict != "INVALID"
    assert not any("html" in f.subject or "render" in f.code for f in rep.findings)


def test_the_contract_does_not_point_at_the_wrong_generator() -> None:
    """`build_walkthrough.py` belongs to `/plan-alignment` and takes a YAML spec.
    Naming it here sends the operator at a script that cannot read these files."""
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")

    render_section = skill.split("### Step 4")[1].split("### Step 5")[0]
    assert "import-mermaid" in render_section  # prose-test: the sentence an operator reads IS the deliverable here
    assert "build_walkthrough.py" in render_section, (  # prose-test: naming the wrong generator is itself the defect
        "the wrong generator must stay NAMED as wrong — removing the mention silently "
        "invites the next author to reach for it")
    assert "Not `build_walkthrough.py`" in render_section  # prose-test: the warning is the contract, not a proxy for one


# ------------------------------------------------------------------ parseability


def test_a_delimiter_in_an_unquoted_label_is_reported(tmp_path: Path) -> None:
    """Found by running `diagram-design`'s extractor over a real drawing, not by
    reading the spec: `ops[Operators: app, tenant, preview]` made it report
    "unterminated statement at line 6" — and this gate had passed the same file,
    because it checked that a block EXISTS and declares the right kind, never that
    it parses.
    """
    from check_design_completeness import unquoted_delimiters

    broken = "flowchart TB\n    ops[Operators: app, tenant]\n    ops --> api"
    assert unquoted_delimiters(broken) == ["Operators: app, tenant"]

    files = dict(GOOD, **{"trust.md": f"# D2\n```mermaid\n{broken}\n```\n"})
    rep = check(_project(tmp_path, files=files))

    assert "unquoted_delimiter_in_label" in [f.code for f in rep.findings]


def test_a_quoted_label_carrying_delimiters_is_fine(tmp_path: Path) -> None:
    """The fix is quoting, and the check must not fire on the fixed form — otherwise
    it flags the very shape it asked for."""
    from check_design_completeness import unquoted_delimiters

    assert unquoted_delimiters('flowchart TB\n    ops["Operators: app, tenant"]') == []


def test_ordinary_labels_do_not_trip_the_check(tmp_path: Path) -> None:
    """A check that fires on normal drawings is a check people disable."""
    from check_design_completeness import unquoted_delimiters

    for line in ("    api[Control API] --> pg[(Postgres)]",
                 "    a -->|writes| b",
                 "    subgraph zone[PLATFORM]",
                 "    state --> other : event"):
        assert unquoted_delimiters(f"flowchart TB\n{line}") == [], line


def test_the_sop_does_not_send_the_operator_at_a_file_nothing_makes() -> None:
    """Step 4 of `SKILL.md` pointed at `build_walkthrough.py` and was corrected; the
    SOP kept telling the operator to open `walkthrough.html`, which nothing generates
    any more. A procedure naming an artifact that does not exist is worse than one
    naming none — the reader assumes the step failed on their machine.
    """
    sop = (Path(__file__).resolve().parents[1] / "SOP.md").read_text(encoding="utf-8")

    assert "walkthrough.html" not in sop  # prose-test: a path to a file nothing makes
    assert "import-mermaid" in sop, (  # prose-test: the operator reads this to find the renderer
        "the render path must be named where the operator reads")


# ------------------------------------------------------------------ the panel


def test_design_is_a_panel_phase() -> None:
    """The user's ask, and the reason it is possible here: a system drawing can be
    audited against code, which a product vision cannot."""
    panel = (Path(__file__).resolve().parents[3] / "rules" / "review-panel.txt")
    text = panel.read_text(encoding="utf-8")

    phases = [ln.split("=", 1)[1] for ln in text.splitlines() if ln.startswith("panel_phases")]
    assert phases and "design" in phases[0]


def test_the_design_panel_spans_two_model_families_or_says_why_not() -> None:
    """Correlated models share failure modes: a plausible fabrication that survives one
    tends to survive its siblings. The seat outside the home family is what the panel
    is for.

    A project that cannot reach a second provider has two honest options — run no panel,
    or run one and say what it is worth — and the second requires a DECLARED waiver in
    `rules/review-panel.txt`, on the layer the installer preserves. A roster that happens
    to be one family and one that was MEANT to be read identically on disk, so this test
    reads the declaration rather than counting families and inferring intent. Without the
    keys, three seats from one family still fails here, in `check_panel_capability.py`
    and at `Panel.tally()`.
    """
    panel = (Path(__file__).resolve().parents[3] / "rules" / "review-panel.txt")
    text = panel.read_text(encoding="utf-8")
    seats = [ln for ln in text.splitlines()
             if ln.startswith("reviewer") and "design" in ln.split("|")[0]]

    assert len(seats) == 3, seats
    # Column 3 is the PROVIDER (`builtin` for every seat); the family comes from the
    # MODEL in column 2, and `review_panel.family_of` is what derives it. Reading
    # column 3 made every roster look like one family — including a roster that spans
    # two — so the waiver branch below fired for a panel that never needed it.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mechanisms" / "cycle"))
    from review_panel import family_of

    families = {family_of(ln.split("|")[2].strip()) for ln in seats}
    if len(families) >= 2:
        return

    waiver = [ln.split("=", 1)[1].strip() for ln in text.splitlines()
              if ln.startswith("single_family_panel")]
    reason = [ln.split("=", 1)[1].strip() for ln in text.splitlines()
              if ln.startswith("single_family_reason")]
    assert waiver and waiver[0] == "accepted", (
        f"the design panel is one family ({families}) and nothing declares that as a "
        f"decision. Add a second family, or declare `single_family_panel = accepted` "
        f"with `single_family_reason`."
    )
    assert reason and reason[0], "a waiver with no reason is not a waiver"


def test_the_cycle_separates_the_panel_from_the_signature() -> None:
    """The first version said "a judge may NOT sign here", which did two jobs at once
    and only one was the argument. `alignment-threshold.md § Amended 2026-09-01`
    separated them: the author must not grade the author's own form was always the
    rule; the reviewer must be human never was."""
    rule = (Path(__file__).resolve().parents[3] / "rules" / "cycle-design.md")
    text = rule.read_text(encoding="utf-8")

    assert "G-D8" in text
    assert "Two gates, two different claims" in text
    assert "A judge may review. A judge may not assume." in text


def test_the_golden_rule_forbids_refusing_an_open_question() -> None:
    """An open question, listed as open, is the phase working. Refuse when one is
    HIDDEN, not when one exists — otherwise the panel teaches people to draw
    placeholders as decisions, which is what the phase exists to prevent."""
    gr = (Path(__file__).resolve().parents[3] / "rules" / "design-golden-rule.md")
    text = gr.read_text(encoding="utf-8")

    assert "Refuse because a question is open" in text
    assert "Refuse when one is **hidden**" in text
    assert "Rewrite the drawing" in text


def test_an_abstention_is_never_agreement() -> None:
    """A reviewer with no code to check against cannot audit R1. Counting that as
    approval would make the panel report coverage it did not have."""
    gr = (Path(__file__).resolve().parents[3] / "rules" / "design-golden-rule.md")

    assert "Counted as incomplete, never as agreement" in gr.read_text(encoding="utf-8")


# ── an absent optional drawing was reported as a present one ─────────────────
#
# `(rep.missing if drawing.mandatory else rep.present).append(...)` put every
# non-mandatory drawing that does not exist into `present`, and `render` tested
# `drawing.key in rep.present` — so `system-map`, the one optional drawing, printed
# `ok  system-map  (derived)` for a file nobody had written.


def test_an_absent_optional_drawing_is_not_reported_as_present(tmp_path: Path) -> None:
    design = tmp_path / ".squad" / "wiki" / "design"
    design.mkdir(parents=True)
    for drawing in DRAWINGS:
        if drawing.mandatory:
            (design / drawing.filename).write_text(
                f"# {drawing.key}\n\n```mermaid\ngraph TD\n  a-->b\n```\n", encoding="utf-8")

    report = check(tmp_path)

    optional = [d.key for d in DRAWINGS if not d.mandatory]
    assert optional, "no optional drawing ships; this test lost its subject"
    for key in optional:
        assert key not in report.present, f"{key} does not exist and is reported present"
        assert key in report.absent_optional, key


def test_the_rendered_line_says_absent_rather_than_ok(tmp_path: Path) -> None:
    design = tmp_path / ".squad" / "wiki" / "design"
    design.mkdir(parents=True)
    for drawing in DRAWINGS:
        if drawing.mandatory:
            (design / drawing.filename).write_text(
                f"# {drawing.key}\n\n```mermaid\ngraph TD\n  a-->b\n```\n", encoding="utf-8")

    rendered = render(check(tmp_path))

    optional = next(d for d in DRAWINGS if not d.mandatory)
    line = next(ln for ln in rendered.splitlines() if optional.key in ln)
    assert "ok " not in line, f"a drawing nobody wrote reads as done: {line!r}"
    assert "absent" in line, line


# ---------------------------------------------- the gate accepted the wrong signer
#
# Measured 2026-09-20 against a complete, covered set of five drawings. The gate
# failed in BOTH directions at once — it agreed a design the agent that draws them
# signed, and refused the one a person signed with their route recorded:
#
#   <!-- signed-by: daedalus-tech-lead -->                    DESIGN_AGREED  exit 0
#   <!-- signed-by: human/paulo (approved in session) -->     AWAITING_REVIEW
#
# `verdict_of` refused the single prefix `judge/`, which is a denylist of one against
# an open set of names; and the local `([^\s>]+)` pattern stopped at the first space,
# so a signature carrying its route captured nothing at all. Both are gone: the gate
# reads `squad.signoff`, which every other gate in the kit now reads too.


def test_the_agent_that_draws_the_design_may_not_agree_it(tmp_path: Path) -> None:
    """`cycle-design.md`: "the signature claims 'I read this and am willing to say it
    holds' — a person, and only a person"."""
    signed = SIGNOFF.replace("- [ ]", "- [x]") + "\n<!-- signed-by: daedalus-tech-lead -->\n"

    rep = check(_project(tmp_path, signoff=signed))

    assert rep.verdict == "AWAITING_REVIEW"


def test_a_signature_keeps_the_route_it_was_given(tmp_path: Path) -> None:
    signed = (SIGNOFF.replace("- [ ]", "- [x]")
              + "\n<!-- signed-by: human/paulo (approved in session) -->\n")

    rep = check(_project(tmp_path, signoff=signed))

    assert rep.signers == ["human/paulo (approved in session)"]
    assert rep.verdict == "DESIGN_AGREED"


def test_deleting_the_checklist_is_not_ticking_it(tmp_path: Path) -> None:
    """Zero boxes is zero unticked boxes, and it is not a review."""
    rep = check(_project(tmp_path, signoff="# Sign-off\n\n## Sign-off\n\n"
                                           "<!-- signed-by: human/paulo -->\n"))

    assert rep.verdict == "AWAITING_REVIEW"


# ------------------------------------------------------------------ coverage
#
# `PIECE-1 not in map_body` is a SUBSTRING test, and `PIECE-1` is a substring of
# `PIECE-10`. Measured 2026-09-20 with eleven pieces and a map naming only PIECE-10
# and PIECE-11: "11 declared, 3 covered by the map". It fails only in the permissive
# direction, and it fires on any product with ten or more pieces.


def test_a_piece_is_not_covered_by_a_longer_id_that_contains_it(tmp_path: Path) -> None:
    pieces = "# Pieces\n\n" + "\n".join(
        f"## PIECE-{i} — thing {i}\n" for i in range(1, 12))
    files = dict(GOOD)
    files["system-map.md"] = ("# D5\n```mermaid\nflowchart TB\n"
                              "    a[PIECE-10 ten]\n    b[PIECE-11 eleven]\n    a --> b\n```\n")

    rep = check(_project(tmp_path, files=files, pieces=pieces))

    assert "PIECE-1" in rep.uncovered, "PIECE-1 is absent from the map; PIECE-10 is not it"
    assert sorted(rep.uncovered) == sorted(f"PIECE-{i}" for i in range(1, 10))


# ------------------------------------------------------------------ the two minors


def test_a_question_mark_placeholder_is_a_placeholder(tmp_path: Path) -> None:
    """`\\b` before `?` needs a word character beside it, and `?` is not one — so
    `???` sat in the pattern and could not match. Same defect as the product scorer's."""
    files = dict(GOOD)
    files["states.md"] = GOOD["states.md"].replace("# D1", "# D1\n\nowner: ???")

    rep = check(_project(tmp_path, files=files))

    assert any(f.code == "placeholder_in_drawing" for f in rep.findings)


def test_a_drawing_that_cannot_be_READ_is_not_a_drawing_that_is_ABSENT(tmp_path: Path) -> None:
    """`_read` swallowed OSError into `""`, so a present-but-unreadable file was
    reported MISSING — which sends a person to draw what they already have."""
    project = _project(tmp_path)
    unreadable = project / ".squad" / "wiki" / "design" / "trust.md"
    unreadable.chmod(0o000)
    try:
        rep = check(project)
    finally:
        unreadable.chmod(0o644)

    assert "trust" not in rep.missing, "it is on disk; it could not be opened"
    assert any(f.code == "drawing_unreadable" for f in rep.findings)


# -------------------------------------------- the phase had no way to reach its end
#
# Three defects that met in one place, measured 2026-09-20:
#
#   1. nothing in the kit writes `design/sign-off.md`. The gate reads it, the SOP says
#      to sign it, and `/sign` refuses what does not exist: "is neither a path that
#      exists nor a slug of any document waiting for a signature. Nothing was signed."
#   2. `$ECO` is used by Step 5 and Step 5b of SKILL.md and assigned nowhere in the
#      file, so both expand to `/skills/...` and `/mechanisms/...` — absolute paths
#      from the filesystem root. The two steps affected are "run the gate" and
#      "convene the panel".
#   3. G-D8 declares a 2-of-3 panel and nothing in the flow ran `check_panel_approval`.
#
# These are prose and template tests. `prompt-text-is-not-behaviour.md` draws the line
# at wording versus structure: an assigned shell variable, a shipped template file and
# a named script invocation are structure.


def test_the_skill_ships_the_checklist_it_asks_a_person_to_sign() -> None:
    template = (Path(__file__).resolve().parents[1] / "templates" / "sign-off.template.md")

    assert template.is_file(), (
        "the gate reads design/sign-off.md and the SOP says to sign it; nothing wrote "
        "one, so DESIGN_AGREED was unreachable")
    body = template.read_text(encoding="utf-8")
    assert "<!-- signed-by: -->" in body, "the unsigned marker a reviewer replaces"
    assert body.count("- [ ] ") >= 3, "a checklist with nothing to tick is not a gate"
    assert "- [x]" not in body, "shipped ticked is shipped signed"


# `test_every_shell_variable_the_skill_uses_is_one_it_assigned` lived here and read
# `skills/design/SKILL.md` alone. It caught the defect in this slice and missed it in
# three others — `plan-alignment`, `release` and `issue-confidence` carried the same
# unassigned `$ECO`, and the one in `plan-alignment` made `classify_alignment_depth.py`
# unrunnable: the script `cycle-plan.md` calls "Derived, never chosen". A test scoped to
# one slice catches the defect in one slice, so it moved to
# `tests/test_a_skill_assigns_the_variables_it_uses.py`, which reads every SKILL.md.


def test_the_flow_runs_the_panel_gate_it_declares() -> None:
    """G-D8 is declared in `cycle-design.md`'s gate table. A gate nothing invokes is a
    claim, and `check_panel_approval.py` exists precisely to refuse an absent record."""
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    sop = (Path(__file__).resolve().parents[1] / "SOP.md").read_text(encoding="utf-8")

    # prose-test: the INVOCATION is the subject here, not the wording around it. G-D8
    # names a script; whether the flow runs it is the question, and a named command in
    # the procedure is the only place that fact lives. `check_gate_mechanisms.py` asks
    # the other half — that a declared gate names an enforcer — and passed throughout,
    # because naming is what it checks.
    assert "check_panel_approval.py" in skill, (  # prose-test: the invocation IS the subject
        "SKILL.md convenes the panel and never checks its verdict, so DESIGN_AGREED "
        "was emitted with no panel record at all")
    assert "check_panel_approval.py" in sop, (  # prose-test: same invocation, operator side
        "the operator's procedure skipped the panel gate entirely")
