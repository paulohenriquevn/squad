# Cycle: DESIGN

Draw the system before any item is filed against it.

## Purpose

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

`.squad/wiki/design/` — five documents, optionally rendered for a review session.

**The mermaid is the drawing.** A rendered file is a reading aid: the gate reads the
fenced block, git versions the fenced block, and an agent reads the fenced block back.
No renderer is required and none is depended on — `archify` validates legibility and
`diagram-design` converts directly, and the phase passes without either.

| Id | File | Mermaid kind | Mandatory |
|---|---|---|---|
| D1 | `design/states.md` | `stateDiagram-v2` | yes |
| D2 | `design/trust.md` | `flowchart` / `graph` | yes |
| D3 | `design/sequence.md` | `sequenceDiagram` | yes |
| D4 | `design/durability.md` | `flowchart` / `graph` / `stateDiagram-v2` | yes |
| D5 | `design/system-map.md` | `flowchart` / `graph` / `C4*` | derived |
| — | `design/sign-off.md` | — | the checklist a person ticks |
| — | *(rendered files)* | — | optional — `archify` or `/diagram-design:import-mermaid`, for a review session. No gate asks for one |

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
| **G-D7** | No human signature | `check_design_completeness.py` |
| **G-D8** | No 2-of-3 panel approval | `review_panel.py` · `check_panel_approval.py` |

## Two gates, two different claims

G-D7 and G-D8 are not redundant, and the first version of this file conflated them —
it said *"a judge may NOT sign here"*, which did two jobs at once and only one of them
was the argument.

`alignment-threshold.md § Amended 2026-09-01` separated exactly these: **the author must
not grade the author's own form** was always the rule; *"the reviewer must be human"*
never was. A judge may review. A judge may not assume.

The panel claims *"nothing here contradicts what we could check"* — three reviewers,
2-of-3, spanning two model families, and a judge may make that claim. The signature
claims *"I read this and am willing to say it holds"* — a person, and only a person.

Both ids are declared once, in the gate table above. Restating them as a second table
made `check_gate_mechanisms.py` read the restatement as a fresh declaration naming no
enforcer, which is the shape it exists to catch and was right to flag.

**Why the panel is possible here when G-B5 refuses one.** A judge grading a product
VISION grades it against nothing — the vision is what everything else is measured
against. A system drawing is different the moment code exists: the code is evidence that
exists independently of the drawing and can contradict it. That is the condition the
amendment names, and it is derived from disk rather than chosen.

With no code yet, the panel audits internal coherence — D5 against the declared pieces,
D3 against D1, D4 against D2 — and may not conclude that the design is RIGHT. A reviewer
that cannot tell which case it is in abstains, and an abstention is counted as an
incomplete panel rather than as agreement.

The contract the reviewers are asked against is
[`design-golden-rule.md`](design-golden-rule.md).

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

## Anti-patterns

Concrete failure modes a reviewer should flag here. This section was absent until
2026-09-17, together with `## Purpose` — the heading above was spelled
`## Why this cycle exists`, the only one of fourteen cycle rules that was. Neither gap
was a decision: `verify_ecosystem.check_cycle_rules` graded six cycles from a hardcoded
tuple, and this file was not in it.

- **Drawing after the items are filed.** The whole point is that both decisions below
  change every component under them. Filed items pin a shape, and the drawing then
  documents what was already assumed instead of deciding it.
- **A drawing with no owner of state.** "Who owns state, and what survives what" is one
  of the two questions this cycle exists to force. A diagram of boxes that does not
  answer it has drawn the parts and skipped the decision.
- **A trust boundary implied rather than drawn.** "Where untrusted code stops" must be a
  line on the drawing. A boundary stated in prose beside the picture is a boundary the
  next reader places somewhere else.
- **Signing a drawing nobody can be wrong about.** `VALID` here means a person put their
  name to a claim. A drawing vague enough that no future state could contradict it costs
  the signature its meaning.
- **Treating DESIGN as per-item.** One item's technical path is `/plan-alignment`. Using
  this cycle for it produces a system drawing scoped to one change, which is not a system
  drawing.

## Cross-references

- The pieces it draws: `skills/brainstorm-pieces/SKILL.md`
- The phase after it: `rules/cycle-backlog.md`
- The per-item equivalent: `skills/plan-alignment/SKILL.md`
- The signature: `skills/sign/SKILL.md`
