"""The generator that replaced hand-placed coordinates.

WHY THESE TESTS EXIST
---------------------
Every defect the hand-drawn version shipped was a LAYOUT defect, and every one of
them was invisible until somebody opened the page: nodes clustered in a corner,
three steps between one pair drawing a single arc, labels stacked, a wire crossing
a node it had no business touching, edges detached from their boxes entirely.

None of that is testable while a human is choosing coordinates — there is no
invariant to violate, only an appearance to dislike. Once Graphviz owns the
geometry there ARE invariants, and these are them: every step gets a route, every
route ends on the box it claims, and the two Graphviz passes agree on one frame
of reference.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import build_walkthrough as bwt  # noqa: E402 — post-bootstrap import

pytestmark = pytest.mark.skipif(
    not shutil.which("dot") or not shutil.which("neato"),
    reason="Graphviz is not installed; the generator cannot lay anything out",
)

SPEC = """
title: Two services
subtitle: a probe
direction: LR
nodes:
  a: { label: Caller, kind: actor }
  b: { label: Service, kind: service }
  c: { label: Store, kind: store }
flows:
  "Happy [primary]":
    - { from: a, to: b, label: request, payload: "{}", note: the note }
    - { from: b, to: c, label: persist }
    - { from: b, to: a, label: "202 accepted" }
    - { from: a, to: b, label: poll }
  "Timeout [exception]":
    - { from: b, to: c, label: persist }
    - { from: b, to: a, label: "504" }
"""


def _spec(tmp_path: Path, body: str = SPEC) -> Path:
    p = tmp_path / "spec.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_every_step_gets_a_route(tmp_path: Path) -> None:
    """A step with no route would draw nothing and say nothing about it."""
    spec = bwt.load_spec(_spec(tmp_path))
    geo = bwt.layout(spec)
    for name, steps in spec.flows.items():
        routes = geo["routed"][name]
        assert len(routes) == len(steps)
        for i, r in enumerate(routes):
            assert "points" in r, f"{name} step {i + 1} has no spline"


def test_routes_and_nodes_share_one_frame(tmp_path: Path) -> None:
    """The defect that detached every edge from every box.

    `neato -n2` does not move pinned nodes, but it DOES renormalise the bounding
    box to what this flow's edges occupy — and a flow with fewer edges needs less
    room. Measured: `agent` pinned at y=388.7 came back at y=220.5, a 168pt shift.
    Each flow therefore arrives in its own translated frame, and the generator has
    to shift it back. This asserts it did: every route must start and end within
    its own node's box.
    """
    spec = bwt.load_spec(_spec(tmp_path))
    geo = bwt.layout(spec)
    h = geo["height"]
    slack = 16.0  # arrowhead clip plus rounding

    for name, steps in spec.flows.items():
        for i, (st, route) in enumerate(zip(steps, geo["routed"][name]), 1):
            pts = [(x, h - y) for x, y in route["points"]]
            for point, nid, which in ((pts[0], st.src, "start"), (pts[-1], st.dst, "end")):
                n = geo["nodes"][nid]
                assert abs(point[0] - n["x"]) <= n["w"] / 2 + slack, \
                    f"{name} step {i} {which} is off {nid} horizontally"
                assert abs(point[1] - n["y"]) <= n["h"] / 2 + slack, \
                    f"{name} step {i} {which} is off {nid} vertically"


def test_the_canvas_is_sized_for_one_flow_not_all_of_them(tmp_path: Path) -> None:
    """A reader sees one flow at a time; the canvas must be sized for that.

    Reserving rank space for every step of every flow sized the gate example at
    867x934 — aspect 0.93, a page that scrolls with unreadable type. One edge per
    PAIR gave 783x210. The generator must stay on the wide side of square.
    """
    spec = bwt.load_spec(_spec(tmp_path))
    geo = bwt.layout(spec)
    assert geo["width"] / geo["height"] > 1.2, \
        f"{geo['width']:.0f}x{geo['height']:.0f} is taller than a flow needs to be"


def test_parallel_steps_between_one_pair_get_separate_routes(tmp_path: Path) -> None:
    """Two hand-patched defects lived here; Graphviz solves it for free.

    The spec walks `a -> b` twice in one flow. If both came back with the same
    spline, the second step would be invisible and its label would sit on the
    first one's — which is exactly what the hand-drawn version did until a lane
    offset was bolted on, and then bolted on again when the first fix cancelled
    itself out.
    """
    spec = bwt.load_spec(_spec(tmp_path))
    geo = bwt.layout(spec)
    routes = geo["routed"]["Happy [primary]"]
    assert routes[0]["points"] != routes[3]["points"], \
        "both `a -> b` steps drew the same curve"


def test_an_unknown_node_is_refused_by_name(tmp_path: Path) -> None:
    """Failing with a name beats failing with a traceback."""
    bad = SPEC.replace("{ from: b, to: c, label: persist }",
                       "{ from: b, to: nowhere, label: persist }")
    spec = bwt.load_spec(_spec(tmp_path, bad))
    assert any("nowhere" in p for p in spec.problems)


def test_a_step_without_a_label_is_refused(tmp_path: Path) -> None:
    """An unnamed edge is a line the reader cannot point at to disagree."""
    bad = SPEC.replace("{ from: b, to: c, label: persist }", "{ from: b, to: c }")
    spec = bwt.load_spec(_spec(tmp_path, bad))
    assert any("no `label:`" in p for p in spec.problems)


def test_a_malformed_spline_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    """Graphviz splines are `1 mod 3` control points. Anything else means the
    format changed, and guessing would draw a plausible wrong line."""
    with pytest.raises(ValueError):
        bwt._bezier_path([[0, 0], [1, 1], [2, 2]], 100.0)


def test_the_generated_page_carries_no_external_reference(tmp_path: Path) -> None:
    """The published page runs behind a CSP that blocks every host but fonts.

    A CDN script here would not fail loudly — the page would render, the
    animation would not, and nobody would know which.
    """
    spec = bwt.load_spec(_spec(tmp_path))
    html = bwt.build(spec)
    for host in ("cdn.", "unpkg", "jsdelivr", "cdnjs"):
        assert host not in html, f"generated page reaches out to {host}"
    assert html.count("<script") == 2, "expected exactly the data block and the shell script"


def test_the_cli_writes_a_file(tmp_path: Path) -> None:
    out = tmp_path / "w.html"
    code = subprocess.call([
        sys.executable, str(SKILL_ROOT / "scripts" / "build_walkthrough.py"),
        str(_spec(tmp_path)), "-o", str(out),
    ])
    assert code == 0
    assert out.exists() and out.stat().st_size > 8_000
