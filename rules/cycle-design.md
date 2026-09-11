# Cycle: DESIGN

Draw the system before any item is filed against it.

## Why this cycle exists

`cycle-brainstorm` ends with `technical-pieces.md`, which names PIECE-N as *"a
responsibility with a boundary"* and states its own limit: *"A piece may map to a repo,
several repos, or part of one. The mapping is not decided here; `/backlog-init`
inventories repos from disk afterwards."*

`cycle-backlog` then opens and items get registered. Between them, nothing draws the
system — so items are filed against a shape that exists only in prose, and the two
decisions no product can retrofit are never forced:

- **who owns state, and what survives what**
- **where untrusted code stops**

Measured against the shape of the problem rather than against a run: both decisions
change every component below them, and both are cheapest to make before the first item
exists.

## Chain

```
/design  →  DESIGN_AGREED  →  /backlog-init
```

**One skill, not five.** The drawings are one act of design; splitting them into phases
would let a person leave the session with the map drawn and the decisions open — which
is the exact failure mode a map-first process produces.

## Position

```
brainstorm  →  DESIGN  →  backlog  →  discover  →  plan  →  implement  → …
```

**Conditional**, on the same terms as `brainstorm`: absent for a scope whose system is
already drawn, and for a repo that adopted the kit before this phase existed. A project
skipping it says so by having no `.squad/wiki/design/`, and `check_design_completeness`
reports `INVALID` with the reason rather than a pass.

## What it produces

`.squad/wiki/design/` — five documents plus a rendered walkthrough.

| Id | File | Mermaid kind | Mandatory |
|---|---|---|---|
| D1 | `states.md` | `stateDiagram-v2` | yes |
| D2 | `trust.md` | `flowchart` / `graph` | yes |
| D3 | `sequence.md` | `sequenceDiagram` | yes |
| D4 | `durability.md` | `flowchart` / `graph` / `stateDiagram-v2` | yes |
| D5 | `system-map.md` | `flowchart` / `graph` / `C4*` | derived |
| — | `sign-off.md` | — | the checklist a person ticks |
| — | `walkthrough.html` | — | rendered, not authored |

**D5 is derived, not drawn first.** A component map produced before the four decisions
is decoration: it looks like design happened and forces no choice.

## Gates

| Gate | What it refuses | Computed by |
|---|---|---|
| **G-D1** | A mandatory drawing absent entirely | `check_design_completeness.py` |
| **G-D2** | A document with no mermaid block — prose about a diagram is not a diagram | `check_design_completeness.py` |
| **G-D3** | A block whose declared kind does not match the slot | `check_design_completeness.py` |
| **G-D4** | A stub: every block under three non-empty lines | `check_design_completeness.py` |
| **G-D5** | A `PIECE-N` with no place in the system map | `check_design_completeness.py` |
| **G-D6** | A placeholder — `TBD`/`TODO`/`FIXME` — in any drawing | `check_design_completeness.py` |
| **G-D7** | No human signature. A judge may NOT sign here | `check_design_completeness.py` |

**G-D7 has the same argument as G-B5.** A judge scoring a system design would be
grading it against the document that declares it, which is the failure the sign-off
exists to prevent. The machine counts drawings and cross-references pieces; whether the
state machine has the RIGHT states is not a countable property.

## Verdicts

| Verdict | Band | Means | Next |
|---|---|---|---|
| `DESIGN_AGREED` | clean | five drawings, every piece covered, signed | `/backlog-init` may run |
| `AWAITING_REVIEW` | orthogonal | complete and covered, nobody signed | a person signs — `/sign` |
| `NEEDS_REVISION` | redo | a stub, a wrong kind, or an uncovered piece | redraw and re-score |
| `INVALID` | structural | a mandatory drawing is absent | draw it; no editing of the others fixes this |

## What this cycle does NOT decide

- **Which repository holds which piece.** That is `/backlog-init`, from disk.
- **Whether a drawing is correct.** No mechanism can. The signature is the claim.
- **How one item will be built.** That is `/plan-alignment`, per item, after DISCOVER
  has evidence — the same instrument at a different level.

## Cross-references

- The pieces it draws: `skills/brainstorm-pieces/SKILL.md`
- The phase after it: `rules/cycle-backlog.md`
- The per-item equivalent: `skills/plan-alignment/SKILL.md`
- The signature: `skills/sign/SKILL.md`
