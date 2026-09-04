# Squad

Two kinds of file live here, and confusing them is the mistake this README exists
to prevent.

## The squad — five roles, versioned, shipped to every consumer

They are **mechanism**: each describes a DECISION, not a repository, so none of them
makes a claim about any consumer's topology. That is why they may be versioned here
when a domain specialist may not.

| Agent | Role | Decides | Runs |
|---|---|---|---|
| `kairos-product-owner` | Product Owner | what work exists, and in what order | `/backlog-item`, `/backlog-review`, `squad_boss.py` |
| `iris-product-designer` | Product Designer (UX/UI) | what the product IS, and what the user will experience — made visible before it is built | `cycle-brainstorm` (4 skills), `/plan-alignment`, `/acceptance` |
| `daedalus-tech-lead` | Tech Lead | one item's technical path — and who builds each part | `/idea-to-release`, the domain specialists |
| `hermes-scrum-master` | Scrum Master / Agile Facilitator | flow: which item enters which lane, and what unblocks a halt | `/pipeline`, `rules/autonomy-envelope.md` |

| `vera-technical-arbiter` | Technical Arbiter | the technical shape of a fix — which principle a problem violates, how severe, and the obvious solution | `vera.py` (emission), the five lenses |
Each carries a name and a temperament, because the temperament is what the file is
for: Kairos is impatient with vagueness, Iris refuses a brief that describes a system
instead of an experience, Daedalus distrusts his own cleverness, Hermes never judges
the work he is moving.

The five do not overlap, and the seams are the point:

```
 Iris ──the product vision──▶ Kairos ──registers & ranks──▶ backlog
   │    (cycle-brainstorm,        │                            │
   │     the one cycle a          │  objectives ──traces_to──▶ │
   │     person attends)          ▼                            ▼
   ├──what the user gets──▶ Hermes ──allocates a lane──▶ Daedalus ──▶ PR
   │   (brief + walkthrough)      │                          │
   │                              │                          ├─▶ domain specialist
   └──────── acceptance, after the release ──────────────────┘   (Developers / QA)
```

**Iris** decides what the product is and what it must feel like, and holds BOTH
alignment gates — product and item; **Kairos** turns that into work and ranks it;
**Hermes** allocates lanes and clears impediments; **Daedalus** executes one item and
hands each domain to the specialist who owns it. A role that could do two of these
would be a role that can overrule itself — Hermes deciding a stage passed, or
Daedalus choosing which item he prefers.

**Iris holding both gates is not one of those overlaps.** They are the same
instrument at two levels, and in neither does she sign: the product sign-off is the
human's, and an item's may be `alignment_judge.py`'s. She produces what is graded and
never grades it.

### Where Developers and QA are

**They are not here, and that is deliberate.** They are the project's own domain
specialists, described in the next section. `daedalus-tech-lead` delegates to them
through `mechanisms/cycle/route_domain.py`, and refuses to stand in for one that does not
exist: a `BROKEN ROUTE` (exit 3) stops the item and becomes work for Kairos, because
a Tech Lead answering for a domain whose invariants nobody wrote is asserting facts
that were never checked.

## Domain specialists — derived per project, never shipped

One agent per domain of the project this kit governs. Each knows the repos it covers, the build commands **verified on disk** rather than copied from a table, the invariants of its domain, and the shapes a real finding takes there.

`domain` on a `B-NNN` item routes to exactly one of them (`rules/cycle-backlog.md § Domain routing`). Work spanning two domains is two items — gate G3.

**This directory ships empty on purpose.** A specialist file describes repositories that exist in *one* ecosystem; shipping someone else's makes gate G1 refuse every item a consumer files, because the map genuinely does not name their repos. Measured on an adopter in 2026-08-18: 88 items carrying real `file:line` evidence, all `BLOCKER/unroutable_repo`. What travels is this README — the mechanism — and the script that derives the routing table.

## Deriving yours

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)   # plugin vs standalone
python3 "$ECO/skills/backlog-init/scripts/detect_domains.py" --root . \
  --write "$ECO/rules/domain-routing.txt"
```

The script reads the topology from disk — not from an inventory, not from a `CLAUDE.md` — and writes the routing table. Then write one file here per domain it names, and `route_domain.py` will resolve them: a domain naming a specialist that is not on disk exits 3 (`BROKEN ROUTE`) rather than reporting a route to nobody.

## Choosing the granularity

One agent per repo duplicates the same facts across every repo that shares a stack, and rots once per copy. One agent per role (backend / frontend / SRE) is too coarse to carry an invariant like "this RDS instance is a protected unit" or "a root `go build ./...` covers nothing here, the repo is multi-module". **The domain is the granularity at which the invariants differ** — that is the line to cut on.

## What each agent is required to carry

1. **Repos verified on disk** — `find -maxdepth 2 -name .git` plus `git -C <repo> rev-list --count HEAD`, never an inventory table.
2. **Build commands that were checked**, with the manifest that proves them.
3. **The domain's invariants** — what is never done here, and why.
4. **The shape of a real finding**, and the false positives this domain generates.
5. **Blast-radius heuristics** — what a change here typically reaches.

Requirement 1 is the one that pays for itself. Two failures found while deriving a real map, both live in that ecosystem's own `CLAUDE.md`: a CLI documented under `pnpm` that actually uses `npm` (a test run under the wrong package manager resolves a different dependency graph than the lockfile pins — green, and testing something other than what ships), and five repos the inventory named that had no checkout a week after it claimed to be verified. Documentation drifts; a routing table naming a repo nobody cloned sends work to a specialist who cannot open the code.

`mechanisms/gates/check_xrefs.py` emits a WARN for any agent here still carrying unfilled sections — a derived skeleton routes correctly and judges nothing, which reads as a specialist that is ready.

## Related

- Routing table: [`rules/cycle-backlog.md`](../rules/cycle-backlog.md)
- Evidence contracts per mode: [`rules/cycle-discover.md`](../rules/cycle-discover.md)
- Live environments: [`rules/live-target.txt`](../rules/live-target.txt)
- Constraint lens: [`rules/current-constraint.md`](../rules/current-constraint.md)
