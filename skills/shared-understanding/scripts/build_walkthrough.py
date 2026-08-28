#!/usr/bin/env python3
"""Build an animated flow walkthrough from a declarative spec.

WHY A GENERATOR AND NOT A TEMPLATE TO HAND-EDIT
-----------------------------------------------
The first version of this artefact asked the author to place every node by hand,
as a percentage of a stage, and drew every edge as a quadratic curve through a
guessed control point. Three defects came out of that in one afternoon, all of
them layout rather than logic: nodes clustered in a corner, three steps between
the same pair of nodes drew one arc with their labels stacked, and neighbouring
nodes produced curves so shallow the labels touched. Each was patched by hand and
the next one appeared, because hand-placement has no invariant to violate — it
only ever looks wrong, and only in the cases you happen to open.

Layout is a solved problem and this script stops re-solving it. Graphviz computes
node positions and true cubic B-spline edge routes, including the separation of
parallel edges between one pair of nodes, which is the exact case that produced
two of those three defects. What is left for this file is the part Graphviz does
not do: the animation and the reading order.

WHY GRAPHVIZ AND NOT ELK, MERMAID OR D2
---------------------------------------
- **ELK** routes orthogonally with real ports and is the better engine, but it is
  JavaScript. Running it at build time needs a Node dependency; running it in the
  page needs ~1MB of library inlined past a CSP that blocks CDNs.
- **Mermaid** renders its own SVG and does not hand back geometry, so an
  animation would have to reverse-engineer the output it just produced.
- **D2** is the closest match and its animation is real, but `--animate-interval`
  cross-fades whole boards; there is no per-step control, no notes panel, and it
  is a Go binary this kit cannot assume.
- **Graphviz** is present on nearly every machine already, emits geometry as JSON
  (`-Tjson`), and its `dot` engine is the layered algorithm architecture diagrams
  want. The generated page then depends on nothing at all.

The engine is a parameter, so `neato`/`fdp`/`circo` are one line away when the
graph is not layered.

WHAT THE ANIMATION DOES, AND WHY THIS AND NOT A MOVING DOT
----------------------------------------------------------
A dot travelling along a line says "something moved". Three coordinated things
say what moved, where from, and what it did on arrival:

1. **The edge draws itself** — `stroke-dashoffset` animated from the path's own
   length to 0. This is the technique the whole field converged on: it is
   GPU-composited, it reads as direction without an arrowhead, and the drawing
   IS the duration, so nothing has to be kept in sync by hand.
2. **A packet rides the same path** — CSS `offset-path` / `offset-distance`
   rather than SMIL `animateMotion`. It composites on the same layer as the
   stroke, it is styleable, and it does not carry `animateMotion`'s trap of
   translating from the element's current position (which parked the packet
   off-screen in the previous version until the coordinates were zeroed).
3. **The destination answers** — the receiving node pulses once, delayed by the
   travel time, so arrival is an event rather than a state that was always true.

`prefers-reduced-motion` collapses all three to the finished state instantly. The
walkthrough is a reading aid; for someone who cannot use motion it must still be
a diagram, not a blank stage.

Usage:
    python3 build_walkthrough.py <spec.yaml> -o <out.html> [--engine dot] [--check]

Exit codes:
    0 — written
    1 — the spec is invalid (every reason is named)
    2 — the spec could not be read, or Graphviz is not installed
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - environment problem, not a code path
    yaml = None

HERE = Path(__file__).resolve().parent
SHELL = HERE.parent / "templates" / "walkthrough-shell.html"

#: Graphviz works in points with y growing UP; SVG grows DOWN. Every coordinate
#: crossing this boundary is flipped exactly once, here.
_PT_PER_INCH = 72.0

#: The four scenario classes a flow may declare. Enforced so the tag in a flow
#: name means the same thing everywhere, and `score_alignment.py` can count them.
SCENARIO_CLASSES = ("primary", "alternate", "exception", "recovery")

NODE_KINDS = ("actor", "service", "store", "external")


@dataclass
class Step:
    src: str
    dst: str
    label: str
    payload: str = ""
    note: str = ""
    path: str = ""          # filled from the layout
    length: float = 0.0     # path length, so the CSS knows its own dash budget


@dataclass
class Spec:
    title: str
    subtitle: str
    nodes: dict[str, dict]
    flows: dict[str, list[Step]]
    direction: str = "LR"
    problems: list[str] = field(default_factory=list)


def load_spec(path: Path) -> Spec:
    """Read the YAML spec and say everything that is wrong with it at once."""
    if yaml is None:
        raise SystemExit("FATAL: PyYAML is required (pip install pyyaml)")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    problems: list[str] = []

    nodes = raw.get("nodes") or {}
    if not nodes:
        problems.append("no `nodes:` — a walkthrough with no nodes draws nothing")
    for nid, n in nodes.items():
        if not isinstance(n, dict) or "label" not in n:
            problems.append(f"node `{nid}` has no `label:`")
        kind = (n or {}).get("kind")
        if kind not in NODE_KINDS:
            problems.append(f"node `{nid}` has kind `{kind}`; expected one of {NODE_KINDS}")

    flows: dict[str, list[Step]] = {}
    for name, raw_steps in (raw.get("flows") or {}).items():
        steps = []
        for i, s in enumerate(raw_steps or [], 1):
            src, dst = s.get("from"), s.get("to")
            for end, who in ((src, "from"), (dst, "to")):
                if end not in nodes:
                    problems.append(f"flow `{name}` step {i}: `{who}: {end}` is not a node")
            if not s.get("label"):
                problems.append(f"flow `{name}` step {i}: no `label:` — the edge has no name")
            steps.append(Step(src, dst, s.get("label", ""),
                              s.get("payload", ""), s.get("note", "")))
        if not steps:
            problems.append(f"flow `{name}` has no steps")
        flows[name] = steps

    if not flows:
        problems.append("no `flows:` — nothing to walk through")

    # Scenario-class coverage is a WARNING here and a scored criterion in
    # score_alignment.py. Refusing to build would stop an author mid-draft, which
    # is exactly when the missing classes are still being discovered.
    tagged = {c for c in SCENARIO_CLASSES
              if any(f"[{c}]" in name.lower() for name in flows)}
    if flows and tagged != set(SCENARIO_CLASSES):
        missing = ", ".join(c for c in SCENARIO_CLASSES if c not in tagged)
        print(f"note: no flow tagged [{missing}] — the defects live in the classes "
              f"nobody drew", file=sys.stderr)

    return Spec(
        title=raw.get("title", "Walkthrough"),
        subtitle=raw.get("subtitle", ""),
        nodes=nodes, flows=flows,
        direction=raw.get("direction", "LR"),
        problems=problems,
    )


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _global_source(spec: Spec) -> str:
    """PASS A — every step of every flow in one graph, to fix node positions.

    Laying each flow out separately would move the nodes between tabs, and a
    reader who has to re-find the same box on every tab is reading a new diagram
    each time. Edge labels are included here even though this pass throws the
    edges away: `dot` reserves rank space for a label, so leaving them out
    produces a layout that is too tight for the labels the next pass will place.
    """
    lines = [
        "digraph W {",
        f"  rankdir={spec.direction}; splines=spline; overlap=false;",
        "  nodesep=0.5; ranksep=1.0; pad=0.3;",
        '  node [shape=box, fixedsize=true, width=1.55, height=0.62];',
        '  edge [fontsize=10];',
    ]
    for nid in spec.nodes:
        lines.append(f"  {_quote(nid)};")

    # One edge per PAIR, carrying that pair's longest label. A reader sees one
    # flow at a time, so reserving rank space for all nineteen steps sizes the
    # canvas for something never on screen: measured on the gate example, the
    # full edge list produced 867x934 (aspect 0.93, a page that scrolls) and the
    # deduplicated one 783x210 (aspect 3.73). Pass B routes the real steps.
    widest: dict[tuple[str, str], str] = {}
    for steps in spec.flows.values():
        for st in steps:
            key = (st.src, st.dst)
            if len(st.label) > len(widest.get(key, "")):
                widest[key] = st.label
    for (src, dst), label in widest.items():
        lines.append(f"  {_quote(src)} -> {_quote(dst)} [label={_quote(label)}];")
    lines.append("}")
    return "\n".join(lines)


def _bezier_path(points: list[list[float]], height: float) -> str:
    """Graphviz control points -> an SVG path, y flipped once.

    The list is `1 mod 3` long: a start point followed by triples. Anything else
    means the format changed and guessing would draw a plausible wrong line.
    """
    if len(points) < 4 or len(points) % 3 != 1:
        raise ValueError(f"unexpected spline with {len(points)} control points")
    fx = lambda p: f"{p[0]:.2f},{height - p[1]:.2f}"  # noqa: E731
    out = [f"M {fx(points[0])}"]
    for i in range(1, len(points), 3):
        out.append(f"C {fx(points[i])} {fx(points[i+1])} {fx(points[i+2])}")
    return " ".join(out)


def _run(engine: str, args: list[str], source: str) -> dict:
    if not shutil.which(engine):
        raise SystemExit(
            f"FATAL: `{engine}` not found. Install Graphviz "
            f"(apt install graphviz / brew install graphviz).")
    proc = subprocess.run([engine, *args, "-Tjson"], input=source,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"FATAL: {engine} failed:\n{proc.stderr.strip()}")
    return json.loads(proc.stdout)


def layout(spec: Spec, engine: str = "dot") -> dict:
    """Two Graphviz passes: positions once, then routes per flow."""
    g = _run(engine, [], _global_source(spec))
    _, _, bw, bh = (float(v) for v in g["bb"].split(","))

    #: Graphviz-frame positions, kept for pass B; the SVG frame is derived below.
    gv_pos: dict[str, tuple[float, float]] = {}
    nodes: dict[str, dict] = {}
    for obj in g.get("objects", []):
        nid = obj.get("name")
        if nid not in spec.nodes:
            continue
        x, y = (float(v) for v in obj["pos"].split(","))
        gv_pos[nid] = (x, y)
        nodes[nid] = {
            "x": round(x, 2), "y": round(bh - y, 2),
            "w": round(float(obj["width"]) * _PT_PER_INCH, 2),
            "h": round(float(obj["height"]) * _PT_PER_INCH, 2),
            "label": spec.nodes[nid]["label"],
            "kind": spec.nodes[nid]["kind"],
        }

    routed: dict[str, list[dict]] = {}
    for fi, (name, steps) in enumerate(spec.flows.items()):
        lines = [
            "digraph F {",
            '  splines=true; overlap=false; sep="+14";',
            '  node [shape=box, fixedsize=true, width=1.55, height=0.62];',
            "  edge [fontsize=10];",
        ]
        for nid, (x, y) in gv_pos.items():
            lines.append(f'  {_quote(nid)} [pos="{x},{y}!"];')
        for si, st in enumerate(steps):
            lines.append(f"  {_quote(st.src)} -> {_quote(st.dst)} "
                         f'[id="s{si}", label={_quote(st.label)}];')
        lines.append("}")

        fg = _run("neato", ["-n2"], "\n".join(lines))

        # `-n2` does not MOVE nodes, but it does renormalise the bounding box to
        # whatever this flow's edges actually occupy — and a flow with fewer
        # edges needs less room, so every flow comes back in its own translated
        # frame. Measured on the primary flow: `agent` was pinned at y=388.7 and
        # came back at y=220.5, a 168pt shift that detached every edge from every
        # box. The offset is constant across nodes, so one node measures it and
        # the routes are shifted back into the frame the positions live in.
        shift_x = shift_y = 0.0
        for obj in fg.get("objects", []):
            nid = obj.get("name")
            if nid in gv_pos:
                nx, ny = (float(v) for v in obj["pos"].split(","))
                shift_x, shift_y = nx - gv_pos[nid][0], ny - gv_pos[nid][1]
                break

        by_id = {}
        for e in fg.get("edges", []):
            eid = e.get("id")
            if not eid:
                continue
            entry: dict = {}
            for op in e.get("_draw_", []):
                if op.get("op") == "b":
                    entry["points"] = [[px - shift_x, py - shift_y] for px, py in op["points"]]
            if "lp" in e:
                lx, ly = (float(v) for v in e["lp"].split(","))
                entry["lp"] = (lx - shift_x, ly - shift_y)
            by_id[eid] = entry
        routed[name] = [by_id.get(f"s{si}", {}) for si in range(len(steps))]

    # Every y flip uses the FINAL height, or edges routed in an earlier pass sit
    # at a different origin from the nodes.
    out_nodes = {nid: {**n, "y": round(bh - gv_pos[nid][1], 2)} for nid, n in nodes.items()}
    return {"width": round(bw, 2), "height": round(bh, 2),
            "nodes": out_nodes, "routed": routed}


def build(spec: Spec, engine: str = "dot") -> str:
    geo = layout(spec, engine)
    h = geo["height"]
    flows = []
    for name, steps in spec.flows.items():
        out_steps = []
        for si, st in enumerate(steps):
            route = geo["routed"][name][si]
            if "points" not in route:
                raise SystemExit(f"FATAL: no route for flow `{name}` step {si + 1}")
            entry = {
                "from": st.src, "to": st.dst, "label": st.label,
                "payload": st.payload, "note": st.note,
                "d": _bezier_path(route["points"], h),
            }
            if "lp" in route:
                lx, ly = route["lp"]
                entry["lx"], entry["ly"] = round(lx, 2), round(h - ly, 2)
            out_steps.append(entry)
        flows.append({"name": name, "steps": out_steps})

    payload = {
        "title": spec.title, "subtitle": spec.subtitle,
        "width": geo["width"], "height": geo["height"],
        "nodes": geo["nodes"], "flows": flows,
    }
    shell = SHELL.read_text(encoding="utf-8")
    if "__PAYLOAD__" not in shell:
        raise SystemExit(f"FATAL: {SHELL} has no __PAYLOAD__ marker")
    # `</script>` inside the JSON would close the tag early and blank the page.
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return shell.replace("__PAYLOAD__", blob).replace("__TITLE__", spec.title)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--engine", default="dot",
                    help="dot (layered, the default) · neato · fdp · circo")
    ap.add_argument("--check", action="store_true",
                    help="validate the spec and lay it out, but write nothing")
    args = ap.parse_args(argv)

    try:
        spec = load_spec(args.spec)
    except OSError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2

    if spec.problems:
        print(f"{len(spec.problems)} problem(s) in {args.spec}:", file=sys.stderr)
        for p in spec.problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    html = build(spec, args.engine)
    if args.check:
        print(f"ok: {len(spec.nodes)} nodes · {len(spec.flows)} flow(s) · "
              f"{sum(len(s) for s in spec.flows.values())} steps · "
              f"{len(html):,} bytes would be written")
        return 0

    out = args.out or args.spec.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html):,} bytes) — {len(spec.nodes)} nodes, "
          f"{len(spec.flows)} flow(s), "
          f"{sum(len(s) for s in spec.flows.values())} steps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
