# Choosing a layout engine

The generator does not place anything. This file is why, which engine it hands
the job to, and when to hand it to a different one.

## Why nothing is placed by hand

The first version of this artefact asked its author to write `x` and `y` as
percentages of a stage. Five defects came out of that in one afternoon, and every
one was layout rather than logic:

| What happened | Why hand-placement could not prevent it |
|---|---|
| Nodes clustered in one corner, two thirds of the canvas empty | Nothing measures emptiness |
| Three steps between one pair drew a single arc, labels stacked 16px apart | Parallel edges are a case the author has to notice |
| A lane offset fixed it, then cancelled itself out — the direction term multiplied the normal's own flip by a second one | Two corrections in the same expression, neither visible in the other's absence |
| A proportional lane gap shrank exactly where nodes were most crowded | The failure mode is invisible until you draw neighbours |
| An edge crossed straight through a node, and its label landed on that node's title | The midpoint of a curve is not a free spot; it is a spot nobody checked |

None of these are testable while a person is choosing coordinates. There is no
invariant to violate — only an appearance to dislike, in the one case you opened.
Once an engine owns the geometry there are invariants, and `tests/` asserts them.

## Why Graphviz

| Engine | Why not |
|---|---|
| **ELK** (`elkjs`) | The better engine — real ports, orthogonal routing, the layered algorithm this problem wants. But it is JavaScript: at build time it needs Node, and in the page it needs ~1MB inlined past a CSP that blocks CDNs. |
| **Mermaid** | Renders its own SVG and hands back no geometry, so an animation would have to reverse-engineer the markup it just produced. |
| **D2** | Closest match, and its animation is genuinely good. But `--animate-interval` cross-fades whole boards: no per-step control, no notes panel, no reader-driven stepping. And it is a Go binary this kit cannot assume. |
| **Manual SVG** | See the table above. |
| **Graphviz** | Already installed nearly everywhere, emits geometry as JSON (`-Tjson`), and `dot` is the layered algorithm. The generated page then depends on nothing at all. |

The decision is not that Graphviz is the best layout engine. It is that Graphviz
is the best layout engine **whose output this kit can consume without adding a
dependency to every consumer**. If the kit ever gains a Node toolchain, ELK's
orthogonal routing with ports is the upgrade, and only `layout()` changes.

## The two passes, and why one is not enough

```
PASS A   dot -Tjson         one graph, one edge per PAIR   -> node positions
PASS B   neato -n2 -Tjson   per flow, positions pinned      -> routes + label spots
```

**Pass A must see every pair**, or nodes would move between tabs and a reader
would be re-finding the same box on every one.

**Pass A must see only one edge per pair.** A reader looks at one flow at a time;
reserving rank space for all nineteen steps sizes the canvas for something never
on screen. Measured on the gate example: every edge gave 867x934 (aspect 0.93, a
page that scrolls, type shrunk to fit), one per pair gave 783x210 (aspect 3.73).

**Pass A must carry the labels anyway.** `dot` reserves rank space for an edge
label; leaving labels out yields a layout too tight for the labels pass B places.

**Pass B must be per flow.** Routing all nineteen at once produces a picture of a
graph nobody reads; routing five produces the picture of the flow being discussed.
`-n2` pins every `pos` and does nothing but route, which also makes the router
avoid the boxes — that is what stopped an edge crossing a node.

## The trap in pass B

`-n2` does not move pinned nodes, but it **does renormalise the bounding box** to
what this flow's edges actually occupy. A flow with fewer edges needs less room,
so every flow comes back in its own translated frame.

Measured: `agent` pinned at `y=388.7` came back at `y=220.5` — a 168pt shift that
detached every edge from every box, while each individual flow still looked
internally consistent. The offset is constant across nodes, so the generator
measures it from one node and shifts the routes back.

`test_routes_and_nodes_share_one_frame` exists for exactly this and would have
caught it in seconds.

## Coordinates

Graphviz works in **points, y growing up**. SVG grows **down**. Every coordinate
crossing that boundary is flipped exactly once, in `_bezier_path` and in the node
loop, using the FINAL canvas height. Flipping with an intermediate height is the
same class of bug as the translation above and looks identical on screen.

## Switching engines

`--engine` changes pass A only:

| Engine | Use when |
|---|---|
| `dot` | The flow has a direction. Almost always — this is the default. |
| `neato` | A mesh with no direction: peers, a service graph, a topology. |
| `fdp` | Larger undirected graphs where `neato` folds in on itself. |
| `circo` | The structure IS a cycle and saying so is the point. |

Pass B is always `neato -n2`, which is not a layout at all.
