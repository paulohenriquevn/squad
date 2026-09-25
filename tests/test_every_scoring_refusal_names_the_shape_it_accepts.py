"""Every scoring gate that refuses an artifact says what shape it would have accepted.

Measured over a 20-hour consumer session, 676 Bash commands: **64 of them — 9% — were
the agent reading a gate's `.py` to learn what shape the gate wanted**, clustered in the
four skills below. The loop was always: run the gate, get refused, open the source, adjust,
run again. The refusals were HONEST — each named what failed — and not ACTIONABLE: none
said what would pass.

`test_a_refusal_names_the_whole_vocabulary_it_wants.py` fixed three refusals one at a
time. This is the CONTRACT that sweep did not write: each scoring gate of the four skills
is fed a malformed artifact, and every item it refuses must reach the output together with
the literal form it accepts. The form is DERIVED — from the headings the gate reads, the
vocabulary it matches, the regex it parses — and the tests below also hold that each
printed example is one the gate's own reader accepts. A shape a reader copies and gets
refused again is the drift #175 found in the concurrency refusal.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SKILLS = _ROOT / "skills"


def _load(relative: str, name: str):
    """A skill script as a module, under a name no other slice uses."""
    path = _SKILLS / relative
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run(relative: str, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(_SKILLS / relative), *args],
                          capture_output=True, text=True, cwd=cwd, timeout=120, check=False)


# ── plan-alignment: score_alignment ─────────────────────────────────────────────────


_ALIGN = "plan-alignment/scripts/score_alignment.py"


def test_the_alignment_refusal_names_the_shape_of_every_gap(tmp_path: Path) -> None:
    sa = _load(_ALIGN, "_shape_score_alignment")
    brief = tmp_path / "empty-alignment.md"
    brief.write_text("# Alignment: nothing yet\n", encoding="utf-8")

    out = _run(_ALIGN, str(brief), cwd=tmp_path).stdout
    report = sa.score_alignment(brief)

    assert report.gaps, "an empty brief must refuse something, or this measures nothing"
    unnamed = [c.key for c in report.gaps if sa.ACCEPTED_SHAPES[c.key] not in out]
    assert not unnamed, f"refused without saying what would pass: {unnamed}\n{out}"


def test_every_alignment_criterion_declares_a_shape(tmp_path: Path) -> None:
    sa = _load(_ALIGN, "_shape_score_alignment")
    brief = tmp_path / "empty-alignment.md"
    brief.write_text("# Alignment\n", encoding="utf-8")

    keys = {c.key for c in sa.score_alignment(brief).criteria}

    assert keys <= set(sa.ACCEPTED_SHAPES), keys - set(sa.ACCEPTED_SHAPES)


def test_the_alignment_shapes_name_every_heading_the_scorer_reads() -> None:
    """Derived, not restated: each alias the reader accepts is in the printed shape."""
    sa = _load(_ALIGN, "_shape_score_alignment")
    for key, headings in sa.SECTION_HEADINGS.items():
        for heading in headings:
            assert f"## {heading}" in sa.ACCEPTED_SHAPES[key], (key, heading)
    for cls in sa._SCENARIO_CLASSES:
        assert f"[{cls}]" in sa.ACCEPTED_SHAPES["scenario_classes"], cls


def test_the_alignment_json_carries_the_shape_beside_the_score(tmp_path: Path) -> None:
    brief = tmp_path / "empty-alignment.md"
    brief.write_text("# Alignment\n", encoding="utf-8")

    out = json.loads(_run(_ALIGN, str(brief), "--json", cwd=tmp_path).stdout)

    assert all(c.get("accepts") for c in out["criteria"] if c["score"] < 2), out["criteria"]


# ── brainstorm-pieces: score_product_alignment ─────────────────────────────────────


_PRODUCT = "brainstorm-pieces/scripts/score_product_alignment.py"


def test_the_product_refusal_names_the_shape_of_every_gap(tmp_path: Path) -> None:
    sp = _load(_PRODUCT, "_shape_score_product")
    (tmp_path / ".git").mkdir()

    out = _run(_PRODUCT, "--root", str(tmp_path), cwd=tmp_path).stdout
    report = sp.score(tmp_path)

    refused = [c for c in report.criteria if c.score < 2]
    assert refused, "an empty product must refuse something, or this measures nothing"
    unnamed = [c.key for c in refused if sp.ACCEPTED_SHAPES[c.key] not in out]
    assert not unnamed, f"refused without saying what would pass: {unnamed}\n{out}"


def test_the_product_block_forms_are_ones_its_reader_accepts() -> None:
    sp = _load(_PRODUCT, "_shape_score_product")
    for pattern, example in ((sp.OBJ_RE, sp.OBJ_FORM), (sp.REQ_RE, sp.REQ_FORM),
                             (sp.PIECE_RE, sp.PIECE_FORM)):
        assert pattern.search(example), (pattern.pattern, example)
    for _key, header in sp.VISION_SECTIONS:
        assert any(f"## {header}" in shape for shape in sp.ACCEPTED_SHAPES.values()), header


# ── discover-confidence: run_opportunity_score ─────────────────────────────────────


_OPPORTUNITY = "discover-confidence/scripts/run_opportunity_score.py"


def _score_opportunity(tmp_path: Path, body: str) -> dict:
    (tmp_path / ".git").mkdir(exist_ok=True)
    doc = tmp_path / "x-opportunity.md"
    doc.write_text(body, encoding="utf-8")
    done = _run(_OPPORTUNITY, str(doc), "--no-warn", cwd=tmp_path)
    return json.loads(done.stdout)


def test_the_opportunity_refusal_names_the_shape_of_every_cap(tmp_path: Path) -> None:
    out = _score_opportunity(tmp_path, "# An opportunity with nothing in it\n")

    assert out["hard_caps_triggered"], "an empty opportunity must be capped"
    shapes = out.get("accepted_shapes", {})
    unnamed = [cap for cap in out["hard_caps_triggered"] if not shapes.get(cap)]
    assert not unnamed, f"capped without saying what would pass: {unnamed}"


def test_a_missing_opportunity_section_is_named_by_its_literal_form(tmp_path: Path) -> None:
    oc = _load("discover-confidence/scripts/check_opportunity_completeness.py",
               "_shape_opportunity_completeness")
    out = _score_opportunity(tmp_path, "# An opportunity with nothing in it\n")
    detractors = " | ".join(out["reasons"]["opportunity_completeness"]["detractors"])

    for name, pattern in oc.MANDATORY_SECTIONS:
        form = oc.SECTION_FORMS[name]
        assert re.search(pattern, form, re.MULTILINE | re.IGNORECASE), (name, form)
        assert form in detractors, (name, form)


def test_every_empty_corner_is_named_with_its_heading(tmp_path: Path) -> None:
    """`[:3]` again: four corners, three named, and the fourth surfaced on the next run."""
    cp = _load("discover-confidence/scripts/check_corners_populated.py",
               "_shape_corners_populated")
    out = _score_opportunity(tmp_path, "# An opportunity with nothing in it\n")
    detractors = " | ".join(out["reasons"]["corner_coverage"]["detractors"])

    for name, pattern in cp.CORNERS:
        form = cp.CORNER_FORMS[name]
        assert re.search(f"^{pattern}", form, re.MULTILINE | re.IGNORECASE), (name, form)
        assert form in detractors, (name, form)


def test_every_cap_the_opportunity_scorer_raises_has_a_shape() -> None:
    """Static, so a cap added later without a shape fails here before any document meets it."""
    ro = _load(_OPPORTUNITY, "_shape_run_opportunity")
    source = (_SKILLS / _OPPORTUNITY).read_text(encoding="utf-8")
    raised = set(re.findall(r'hard_caps_triggered\.append\("([a-z_]+)"\)', source))
    raised |= {f"empty_corner_{name}" for name, _ in
               _load("discover-confidence/scripts/check_corners_populated.py",
                     "_shape_corners_populated").CORNERS}

    assert len(raised) > 4, "the cap scan found too little; this test needs re-pointing"
    missing = sorted(cap for cap in raised if not ro.accepted_shape(cap, {}))
    assert not missing, f"caps with no accepted shape: {missing}"


def test_the_evidence_shape_is_one_the_pointer_reader_accepts() -> None:
    ep = _load("discover-confidence/scripts/check_evidence_pointers.py",
               "_shape_evidence_pointers")
    assert ep.CODE_POINTER_RE.search(ep.CODE_POINTER_FORM), ep.CODE_POINTER_FORM
    assert ep.RUNTIME_OBS_RE.search(ep.RUNTIME_OBS_FORM), ep.RUNTIME_OBS_FORM


# ── plan-confidence: run_structural ────────────────────────────────────────────────


_PLAN = "plan-confidence/scripts/run_structural.py"

_UNREADABLE_MATRIX_PLAN = (
    "# Plan: nothing\n\n## Coverage Matrix\n\n| Thing | Where |\n|---|---|\n| x | y |\n\n"
    "## Tasks\n\n### T1.1 — do it\n\nFixes a regression in the parser bug path.\n\n"
    "## ADRs\n\n### D1 — pick one\n\nWe chose it.\n"
)


def _score_plan(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / ".git").mkdir(exist_ok=True)
    plan = tmp_path / "x-plan.md"
    plan.write_text(body, encoding="utf-8")
    return _run(_PLAN, str(plan), "--no-warn", "--no-code-quality", "--structural-only",
                cwd=tmp_path)


def test_the_plan_refusal_names_the_shape_of_every_cap(tmp_path: Path) -> None:
    out = json.loads(_score_plan(tmp_path, _UNREADABLE_MATRIX_PLAN).stdout)

    assert out["hard_caps_triggered"], "a malformed plan must be capped"
    shapes = out.get("accepted_shapes", {})
    unnamed = [cap for cap in out["hard_caps_triggered"] if not shapes.get(cap)]
    assert not unnamed, f"capped without saying what would pass: {unnamed}"


def test_an_unreadable_matrix_names_both_column_vocabularies(tmp_path: Path) -> None:
    cm = _load("plan-confidence/scripts/check_coverage_matrix.py", "_shape_coverage_matrix")
    out = json.loads(_score_plan(tmp_path, _UNREADABLE_MATRIX_PLAN).stdout)
    shape = out["accepted_shapes"]["coverage_matrix_unreadable"]

    for header in (*cm.TASK_COLUMN_HEADERS, *cm.GAP_COLUMN_HEADERS):
        assert header in shape.lower(), (header, shape)


def test_a_plan_with_no_matrix_is_told_the_table_it_needs(tmp_path: Path) -> None:
    cm = _load("plan-confidence/scripts/check_coverage_matrix.py", "_shape_coverage_matrix")
    done = _score_plan(tmp_path, "# Plan: nothing\n\n## Tasks\n- do it\n")

    assert done.returncode == 2
    assert "## Coverage Matrix" in done.stderr
    assert cm.TASK_COLUMN_HEADERS[0] in done.stderr.lower(), done.stderr
    assert cm.GAP_COLUMN_HEADERS[0] in done.stderr.lower(), done.stderr


def test_every_cap_the_plan_scorer_names_has_a_shape() -> None:
    """Static, so a cap added later without a shape fails here before any plan meets it."""
    rs = _load(_PLAN, "_shape_run_structural")
    source = (_SKILLS / _PLAN).read_text(encoding="utf-8")
    literal = set(re.findall(r'"((?:soft_floor_)?[a-z]+(?:_[a-z0-9]+)+)"', source))
    raised = {cap for cap in literal
              if re.search(rf'append\(\(?"{cap}"|append\(f?"{cap}"', source)}
    raised |= {f"soft_floor_{reason}" for reason in ("smell_density_high",
                                                    "high_deferred_ratio")}
    raised |= set(rs.DYNAMIC_CAP_IDS)

    assert raised, "the cap scan found nothing; this test needs re-pointing"
    missing = sorted(cap for cap in raised if not rs.accepted_shape(cap))
    assert not missing, f"caps with no accepted shape: {missing}"


# ── plan-alignment: build_walkthrough ───────────────────────────────────────────────


def test_an_empty_walkthrough_spec_is_told_the_node_and_flow_shapes(tmp_path: Path) -> None:
    """`no nodes:` named the key and not what goes under it; the node kinds were printed
    only once a node existed with the wrong one."""
    pytest.importorskip("yaml")
    bw = _load("plan-alignment/scripts/build_walkthrough.py", "_shape_build_walkthrough")
    spec = tmp_path / "spec.yaml"
    spec.write_text("title: nothing\n", encoding="utf-8")

    problems = " | ".join(bw.load_spec(spec).problems)

    for kind in bw.NODE_KINDS:
        assert kind in problems, (kind, problems)
    for key in ("label:", "from:", "to:"):
        assert key in problems, (key, problems)
