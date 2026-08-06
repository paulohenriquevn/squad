#!/usr/bin/env python3
"""Derive architecture rules a repo ALREADY obeys, so adopting them costs nothing.

## The problem this solves

Writing architecture rules for a repo you did not build means deciding what its architecture is.
Do that from taste and you produce a gate that reports violations which are evidence of nothing —
the defect gate G5 rejects when prior art is offered as justification.

## The criterion

An edge that is already one-way is a measured invariant, not an opinion. If `tui/` imports
`agents/` forty times and `agents/` imports `tui/` zero times, then "agents must not import tui"
is *already true*; writing it down changes no code and freezes a property the repo has. If both
directions carry traffic, there is no invariant to freeze and this tool proposes nothing.

usetheo-labs/agent-builder states the same rule of adoption from the other side:

    "Nenhuma destas regras foi escrita contra violacao existente: as cinco sairam de 0 violacoes
     no commit que as introduziu, o que significa que elas CONGELAM um estado bom em vez de
     anunciar divida."

So a candidate that would fail on day one is NOT proposed as a gate. It is a finding — someone
has to decide whether the crossing is a defect or the architecture — and that decision belongs in
the backlog, not in a config file.

## The guard that matters most

An empty graph would make every pair look one-way and this tool would propose a full rule set
built on having parsed nothing. `extract_imports_and_calls` degrades to an empty list when
tree-sitter is missing, so that failure is reachable. `propose` refuses on an empty graph rather
than answering confidently about a codebase it never read.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
_CODE_QUALITY_SCRIPTS = _SKILL_ROOT.parent / "code-quality"
if str(_CODE_QUALITY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_CODE_QUALITY_SCRIPTS))

#: Directories that are never architectural units.
_NOT_A_UNIT = frozenset(
    {
        "node_modules", "vendor", "target", "dist", "build", ".git", ".claude",
        "testdata", "__pycache__", "coverage", "docs", "examples", "scripts",
    }
)

_GO_LIST_TIMEOUT_SEC = 180


@dataclass(frozen=True)
class Edge:
    """One directed dependency between two top-level units, with how often it occurs."""

    source: str
    target: str
    count: int


@dataclass
class Graph:
    """The dependency graph between a repo's top-level units."""

    units: set[str] = field(default_factory=set)
    edges: dict[tuple[str, str], int] = field(default_factory=dict)
    #: Units the scan SAW, whether or not they have edges. This is what separates "we read the
    #: repo and it has no cross-imports" from "we read nothing" — two states that look identical
    #: from the edge count alone, and only one of which permits a conclusion.
    units_seen: set[str] = field(default_factory=set)

    def see(self, unit: str) -> None:
        """Record that the scan reached this unit, edges or not."""
        if unit:
            self.units_seen.add(unit)

    def add(self, source: str, target: str) -> None:
        if source == target or not source or not target:
            return
        self.units.update({source, target})
        self.edges[(source, target)] = self.edges.get((source, target), 0) + 1

    def count(self, source: str, target: str) -> int:
        return self.edges.get((source, target), 0)

    @property
    def total_edges(self) -> int:
        return sum(self.edges.values())


@dataclass(frozen=True)
class Candidate:
    """A rule the repo already obeys, with the measurement that says so."""

    kind: str
    source: str
    target: str
    evidence: str


def one_way_candidates(graph: Graph) -> list[Candidate]:
    """Every ordered pair where traffic flows one way and the reverse is empty.

    The reverse direction being empty is the whole claim. It is checked, not assumed, and the
    count that proves it goes into the evidence string so the rule carries its own justification
    into the config file.
    """
    out: list[Candidate] = []
    for source in sorted(graph.units):
        for target in sorted(graph.units):
            if source == target:
                continue
            forward = graph.count(source, target)
            backward = graph.count(target, source)
            if forward > 0 and backward == 0:
                out.append(
                    Candidate(
                        kind="one-way",
                        source=target,  # the side that must NOT import
                        target=source,  # the side it must not import
                        evidence=(
                            f"{source} -> {target} carries {forward} import(s); "
                            f"{target} -> {source} carries 0. The rule freezes what already holds"
                        ),
                    )
                )
    return out


def independent_pairs(graph: Graph) -> list[Candidate]:
    """Units that carry traffic elsewhere but never to each other.

    Both directions empty is as measured as one direction empty, and it states something stronger:
    these two are siblings, and neither is a library of the other. Written by hand in
    usetheo-labs/agent-builder as `superficies-nao-se-importam`, with the reasoning that code both
    need belongs in a third place — so the rule is what keeps the third place necessary.

    Restricted to units that participate in the graph at all. Two directories with no edges in any
    direction are not siblings, they are unrelated, and a rule between them would govern nothing.
    """
    active = {u for edge in graph.edges for u in edge}
    out: list[Candidate] = []
    ordered = sorted(active)
    for i, left in enumerate(ordered):
        for right in ordered[i + 1 :]:
            if graph.count(left, right) or graph.count(right, left):
                continue
            out.append(
                Candidate(
                    kind="siblings",
                    source=left,
                    target=right,
                    evidence=(
                        f"{left} and {right} both take part in the graph and exchange 0 imports "
                        "in either direction. Neither is a library of the other; what both need "
                        "belongs somewhere they share"
                    ),
                )
            )
    return out


def find_cycles(graph: Graph) -> list[tuple[str, ...]]:
    """Every directed cycle between units, as sorted tuples so duplicates collapse.

    A cycle is the one finding here that is never a matter of architecture taste: the Acyclic
    Dependencies Principle does not have a "unless you meant it" clause. Its presence is why
    `no-circular` is proposed only when the count is zero — proposing it against existing cycles
    would ship a config that fails on the first run.
    """
    seen: set[tuple[str, ...]] = set()
    path: list[str] = []
    on_path: set[str] = set()

    def walk(unit: str) -> None:
        if unit in on_path:
            cycle = path[path.index(unit) :]
            seen.add(tuple(sorted(cycle)))
            return
        if len(path) > len(graph.units):
            return
        path.append(unit)
        on_path.add(unit)
        for (source, target) in graph.edges:
            if source == unit:
                walk(target)
        path.pop()
        on_path.discard(unit)

    for unit in sorted(graph.units):
        walk(unit)
    return sorted(seen)


def propose(graph: Graph) -> dict:
    """Turn a measured graph into rule candidates, or refuse if there is no graph.

    The refusal is not politeness. A tool that answers confidently about a codebase it failed to
    read is the exact failure mode the D5 meta-gate exists to catch, and it would be absurd to
    build that gate and then ship it inside this.
    """
    if graph.total_edges == 0:
        if len(graph.units_seen) < 2:
            return {
                "status": "refused",
                "reason": (
                    f"the scan reached {len(graph.units_seen)} unit(s) and found no imports at "
                    "all. Either the parser did not run — tree-sitter degrades to an empty "
                    "result rather than failing — or there is nothing here to govern. Proposing "
                    "from an empty graph would make every pair look one-way, so nothing is "
                    "proposed until the graph is real."
                ),
                "units": sorted(graph.units_seen),
                "candidates": [],
            }
        return {
            "status": "proposed",
            "units": sorted(graph.units_seen),
            "total_edges": 0,
            "cycles": [],
            "candidates": [
                {
                    "kind": "independence",
                    "forbid": "any import between units",
                    "evidence": (
                        f"the scan reached {len(graph.units_seen)} units and measured 0 imports "
                        "between them. Mutual independence is a stronger property than any "
                        "direction rule, and it is the one most easily lost by accident"
                    ),
                }
            ],
            "not_proposed": [],
        }

    cycles = find_cycles(graph)
    candidates = [
        {"kind": c.kind, "forbid": f"{c.source} -> {c.target}", "evidence": c.evidence}
        for c in one_way_candidates(graph)
    ] + [
        {"kind": c.kind, "forbid": f"{c.source} <-> {c.target}", "evidence": c.evidence}
        for c in independent_pairs(graph)
    ]
    if not cycles:
        candidates.insert(
            0,
            {
                "kind": "no-circular",
                "forbid": "any cycle",
                "evidence": (
                    f"0 cycles across {len(graph.units)} units and {graph.total_edges} edges "
                    "measured now. The rule keeps it that way without anyone remembering to look"
                ),
            },
        )

    return {
        "status": "proposed",
        "units": sorted(graph.units),
        "total_edges": graph.total_edges,
        "cycles": [list(c) for c in cycles],
        "candidates": candidates,
        "not_proposed": (
            []
            if not cycles
            else [
                {
                    "kind": "no-circular",
                    "reason": (
                        f"{len(cycles)} cycle(s) exist today, so this rule would fail on its first "
                        "run. That is a finding for the backlog, not a gate to adopt"
                    ),
                }
            ]
        ),
    }


# ---------------------------------------------------------------------------
# Graph construction, per language
# ---------------------------------------------------------------------------


def go_graph(manifest_dir: Path) -> Graph:
    """Build the unit graph from `go list -json ./...`.

    The Go toolchain resolves imports exactly, so this needs no third-party parser and cannot
    silently under-read the way a regex scan can.
    """
    graph = Graph()
    try:
        result = subprocess.run(
            ["go", "list", "-json", "./..."],
            cwd=str(manifest_dir),
            capture_output=True,
            text=True,
            timeout=_GO_LIST_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return graph
    if result.returncode != 0 or not result.stdout.strip():
        return graph

    module = ""
    packages = list(_iter_json_objects(result.stdout))
    for pkg in packages:
        module = module or str(pkg.get("Module", {}).get("Path", ""))
    if not module:
        return graph

    for pkg in packages:
        source = _unit_of_import(str(pkg.get("ImportPath", "")), module)
        graph.see(source)
        for imported in pkg.get("Imports") or []:
            target = _unit_of_import(str(imported), module)
            if target:
                graph.add(source, target)
    return graph


def typescript_graph(manifest_dir: Path) -> Graph:
    """Build the unit graph from the repo's own source, via the shared tree-sitter extractor.

    Only relative imports count. A bare specifier is a package, not a unit of this repo, and
    treating `react` as a unit would invent architecture out of the dependency list.
    """
    from scripts.check_symbol_fab import extract_imports_and_calls  # noqa: PLC0415

    graph = Graph()
    for path in sorted(manifest_dir.rglob("*")):
        if path.suffix not in {".ts", ".tsx", ".mts"} or not path.is_file():
            continue
        if any(part in _NOT_A_UNIT for part in path.parts) or ".test." in path.name:
            continue
        source = _unit_of_path(path, manifest_dir)
        if not source:
            continue
        graph.see(source)
        for symbol in extract_imports_and_calls(path, "typescript"):
            module = getattr(symbol, "module", "") or ""
            if not module.startswith("."):
                continue
            resolved = (path.parent / module).resolve()
            try:
                target = _unit_of_path(resolved, manifest_dir.resolve())
            except ValueError:
                continue
            if target:
                graph.add(source, target)
    return graph


def _iter_json_objects(stream: str):
    """`go list -json` emits concatenated objects, not an array."""
    decoder = json.JSONDecoder()
    index = 0
    text = stream.strip()
    while index < len(text):
        try:
            obj, offset = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            return
        yield obj
        index = offset
        while index < len(text) and text[index] in " \n\r\t":
            index += 1


def _unit_of_import(import_path: str, module: str) -> str:
    """First path segment under the module root. External imports are not units."""
    if not import_path.startswith(module):
        return ""
    rest = import_path[len(module) :].lstrip("/")
    if not rest:
        return ""
    head = rest.split("/", 1)[0]
    return "" if head in _NOT_A_UNIT else head


def _unit_of_path(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return ""
    head = rel.parts[0] if rel.parts else ""
    return "" if head in _NOT_A_UNIT or head == rel.name else head


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: propose_rules.py <repo-path> [--language go|typescript]", file=sys.stderr)
        return 2
    repo = Path(args[0]).resolve()
    language = args[args.index("--language") + 1] if "--language" in args else _detect(repo)
    if language is None:
        print(json.dumps({"status": "refused", "reason": "no supported manifest at the repo root"}))
        return 0

    graph = {"go": go_graph, "typescript": typescript_graph}[language](repo)
    result = propose(graph)
    result["language"] = language
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _detect(repo: Path) -> str | None:
    if (repo / "go.mod").is_file():
        return "go"
    if (repo / "package.json").is_file():
        return "typescript"
    return None


if __name__ == "__main__":
    raise SystemExit(main())
