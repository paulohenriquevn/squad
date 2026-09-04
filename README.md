<div align="center">

# Squad

**Maintain a running ecosystem on measurements, not hunches.**

[![Status](https://img.shields.io/badge/status-alpha-orange)](CHANGELOG.md)
[![Version](https://img.shields.io/badge/version-0.1.0-blue)](.claude-plugin/plugin.json)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)](pyproject.toml)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-blueviolet)](https://code.claude.com/docs/en/)

A development squad that keeps a running ecosystem healthy: domain specialists you derive from your own repositories, and a pipeline that carries a maintenance item from **hunch → measurement → plan → code → merge**. Every item starts as a hypothesis. Nothing reaches a plan until somebody measured it — and finding nothing is a successful outcome.

[Quick start](#quick-start) · [How it works](#how-it-works) · [The specialists](#the-specialists) · [Contributing](CONTRIBUTING.md)

</div>

---

## Table of contents

- [Why this exists](#why-this-exists)
- [The one phase with a human in it](#the-one-phase-with-a-human-in-it)
- [What you get](#what-you-get)
- [How it works](#how-it-works)
- [The specialists](#the-specialists)
- [Quick start](#quick-start)
- [The four discover modes](#the-four-discover-modes)
- [Project structure](#project-structure)
- [Advisory skills](#advisory-skills)
- [Unbreakable principles](#unbreakable-principles)
- [Relationship to Cycle](#relationship-to-cycle)
- [Status](#status) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [License](#license)

---

## Why this exists

Maintaining a live multi-repo ecosystem fails in ways that building a new one does not:

1. **Work justified by hunches.** "The trace explorer feels slow" becomes a refactor nobody sized, because nobody measured what was slow.
2. **Fabricated evidence.** A `file:line` nobody opened, a status code nobody requested, a test asserted to fail but never run. Everything downstream treats it as fact.
3. **Findings that die orphaned.** A review notices six real problems; they live in a report, get read once, and never become work.
4. **Local optimisation.** Ten well-evidenced improvements shipped into a stage that was never the limit, mistaken for throughput.
5. **Generic agents.** A reviewer that does not know a root `go build ./...` covers almost nothing in a multi-module repo reports "builds clean" and has measured nothing.

Squad addresses each with a phase, a gate, or a specialist who knows the difference.

## The one phase with a human in it

Everything from `/backlog-init` down runs unattended. That is only defensible if
somebody agreed, once, on what is being built — otherwise the chain executes hunches
at speed and the throughput reads as progress.

`cycle-brainstorm` is where that agreement is made, and it is the **only** cycle in
the kit that requires a person:

```bash
/brainstorm-vision       # what it is, who for, and what it is NOT
/brainstorm-objectives   # OBJ-N, each with a metric containing a number
/brainstorm-trd          # REQ-N, each citing the objective it serves
/brainstorm-pieces       # PIECE-N + the gate: 90% and a PERSON's signature
```

Four documents land in `wiki/product/`, and every backlog item afterwards traces to
an `OBJ-N`. That traceability makes two questions computable that were impressions
before: **an objective nothing serves**, and **shipped work serving no objective**.
Both become the agenda of the next session, which `build_agenda.py` assembles before
the first question is asked — along with every item that halted, routed nowhere, or
stalled on a decision only a person can make.

**A judge may not sign this one.** `alignment_judge.py` signs an item's alignment
brief when nobody is coming, because it reads the item's evidence. A product vision
has no independent evidence — it is what everything else is measured against — so a
judge scoring it would grade the document against itself. The scorer enforces that:
a `signed-by: judge/…` returns `AWAITING_REVIEW`.

## What you get

- **A hunch is registerable, and cheap.** `/backlog-item` takes an unmeasured hypothesis — no evidence required, on purpose. Demanding proof at intake silences the cheapest signal a maintenance team has.
- **Measurement decides, not conviction.** The DISCOVER chain (`/discover-plan` → `/discover-edge-cases` → `/discover-plan-confidence` → `/discover-execute` → `/discover-confidence`) runs against *our* code and runtime in one of four modes, and has the authority to **kill** the item. A run that finds nothing protected the plan cycle from a hunch.
- **Prior art can never be evidence.** Gate G5 rejects "project X does it this way" as a justification. Knowing how others solved it is fine; it is simply not a measurement of our system.
- **Pointers are verified, line included.** A cited `file:line` that does not resolve — missing file, or a line past the end of one — caps the artifact at INVALID.
- **One registry, two producers.** `BACKLOG.md` is the single answer to "what is pending?". Humans file items; sweeps register findings with evidence attached. Orphaned findings have nowhere to hide.
- **Eight specialists who know the terrain.** Each carries build commands verified on disk, the domain's invariants, and the false positives that domain generates.
- **A boundary that stopped working does not pass silently.** Every architecture linter goes green when a rule names a directory that moved — measured on two adopters, one Go and one TypeScript. `/arch-check` and the D5 detector report it; nothing else does.
- **Guardrails at runtime.** Claude Code hooks enforce git safety (no `--force`, no direct-to-`main`), TDD discipline, CHANGELOG hygiene and honest public copy while you work.

## How it works

```
        ┌──────────────────────────────────────────────┐
        │  BRAINSTORM · /brainstorm-vision  (phase −1) │
        │  → objectives → trd → pieces                 │
        │  THE ONLY PHASE A HUMAN ATTENDS              │
        │  gate: 90% + a person's signature            │
        └────────────────────┬─────────────────────────┘
                             │ PRODUCT_ALIGNED
                             ▼
        ┌──────────────────────────────────────────────┐
        │  BACKLOG · /backlog-item          (phase 0)  │
        │  a hypothesis. evidence: none-yet            │
        └────────────────────┬─────────────────────────┘
                             │ B-NNN · status: raw
                             ▼
        ┌──────────────────────────────────────────────┐
        │  DISCOVER · /discover-plan B-NNN --mode {…}  │
        │  measures OUR code / OUR runtime             │
        ├──────────────────────┬───────────────────────┤
        │  evidence found      │  nothing found        │
        │  → status: triaged   │  → status: killed     │
        └──────────┬───────────┴───────────────────────┘
                   │                    ✔ a successful outcome
                   ▼
        ┌──────────────────────────────────────────────┐
        │  PLAN → IMPLEMENT → CODE-QUALITY → REVIEW    │
        │  → RELEASE          (TDD, gates, jury)       │
        └────────────────────┬─────────────────────────┘
                             │ RELEASED
                             ▼
        ┌──────────────────────────────────────────────┐
        │  ACCEPTANCE · /acceptance M<N>               │
        │  exercises the RELEASED delivery as a user   │
        │  meets it — the only gate that flips [ ]→[x] │
        └────────────────────┬─────────────────────────┘
                             │ ACCEPTED
                             ▼
                   status: shipped ──→ back to SELECT
```

The macro loop (`cycle-maintenance`) selects the next item — measured before unmeasured, then oldest first — routes it to a specialist, and delegates. **It never reports "complete".** A backlog is not a scope; an empty one means nobody has looked recently, so the empty state is a prompt to sweep.

## The specialists

**You derive yours; the kit ships none.** A specialist file describes
repositories that exist in *one* ecosystem, so what travels is the routing
MECHANISM (`agents/README.md`) with the map left empty — a consumer that
inherits someone else's table has gate G1 refuse every item it files, which was
measured on an adopter in 2026-08-18: 88 items with real `file:line` evidence,
all `unroutable_repo`.

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)   # plugin vs standalone
python3 "$ECO/skills/backlog-init/scripts/detect_domains.py" --root . \
  --write "$ECO/rules/domain-routing.txt"
```

The script reads the topology from disk and writes the table; then write one
file per domain it names, under `agents/`. Each specialist carries the repos it
covers, the build commands **verified on disk** rather than copied from a table,
the invariants of its domain, and the shape a real finding takes there. Cut the
domains at the granularity where those invariants differ — one agent per repo
rots once per copy, one agent per role is too coarse to hold "this RDS instance
is a protected unit".

Routing is deterministic (`mechanisms/cycle/route_domain.py`) and reads its table from
`rules/cycle-backlog.md` — one table, one truth. A domain naming a specialist
that is not on disk exits 3 (`BROKEN ROUTE`) rather than reporting a route to
nobody. See [`agents/README.md`](agents/README.md).

## Quick start

**Requirements:** Python 3.10+, `git`, Claude Code, and the `ralph-loop` plugin for halt-loop phases.

**What the kit assumes about your repo.** These are not configurable, so check them before adopting:

| Assumption | Why it matters |
|---|---|
| Branching `workspace → develop → trunk` | `hooks/validate-command.py` blocks commits on the trunk and on `develop`. The trunk is detected — `main`, `master`, or whatever `origin/HEAD` points at — so a repo on `master` is protected too |
| `gh` CLI, authenticated | `/release` opens the develop→trunk PR through it |
| `CHANGELOG.md`, Keep a Changelog format | The Rule 6 gate activates when the file exists; without it the Stop hook says so rather than passing silently |
| Go, Python, TypeScript or Rust | Only these have `code-quality` detectors. Other stacks run the rest of the pipeline fine |

**Adopting it in another project is a bootstrap, not just an install.** The kit ships *this*
ecosystem's domain routing table, and gate G1 refuses every item until you replace it — measured on
an adopter: 88 items with real `file:line` evidence, all `BLOCKER/unroutable_repo`. After
`mechanisms/distribution/install.sh`, run `detect_domains.py --root . --write` and write the specialist files it
names. The installer prints the sequence.

```bash
# 1. Create the registry, once (inventories repos FROM DISK, never from a table)
/backlog-init

# 2. Register something worth looking at — a hunch is enough
/backlog-item trace-explorer-feels-slow

# 3. Measure it. This may kill the item, and that is a good day
/discover-plan B-014 --mode live-test   # what will be measured, and what would kill it
/discover-edge-cases B-014              # what could make the measurement lie
/discover-plan-confidence B-014         # is the plan ready to run?
/discover-execute B-014                 # run it — may emit ITEM_KILLED
/discover-confidence B-014              # is the finding solid enough to act on?

# 4. If it survived, run the chain
/idea-to-release B-014
```

Sweep a whole domain instead of filing by hand:

```bash
/discover-execute --sweep data-plane-ts   # findings land in BACKLOG.md with evidence attached
/backlog-review                        # what has rotted in the registry
```

## The four discover modes

Each mode defines what counts as a measurement. Evidence from one does not satisfy another.

| Mode | Finds | Evidence required |
|---|---|---|
| `review` | A defect visible in our code | `file:line` + the rule violated + why it matters **here** |
| `live-test` | Behaviour wrong in the running system | `METHOD URL -> status`, console, trace id, timing, screenshot |
| `bug` | A reproduced defect | Numbered repro **plus a test that fails on the current state, executed** |
| `evolve` | Measured cost of the status quo | A number: N round-trips, N duplicated call sites, N ms |

`bug` has a hard floor: **no failing test, no bug.** A defect nobody can express as a failing test is not understood well enough to fix. `live-test` refuses on a domain with no declared target — six of eight have none, by design, because a Go library and a Terraform module have no surface a browser can probe.

## Project structure

Every directory is named for what it holds, and the name is checked:
`mechanisms/gates/check_semantic_names.py` runs in CI and refuses a name that says
nothing — a `lib/`, a `utils/`, a test filed outside a test tree.

```
squad/
├── wiki/product/    ← what the product IS. Four documents, agreed with a person
├── rules/           ← the contracts. What each cycle promises and which gates block it
│   └── squad-map.md          ← the 360º view: every phase, who owns it, what it reads
│   ├── cycle-*.md            ← one per phase; the source of truth for that phase
│   ├── cycle-phases.txt      ← the chain itself, declared once and machine-readable
│   ├── records-location.md   ← where output goes, and why the split below exists
│   └── live-target.txt       ← declared live environments
├── skills/          ← what the agent can DO. One directory per capability
├── mechanisms/      ← what COMPUTES the verdicts. No verdict is asserted in prose
│   ├── gates/                ← everything that measures the kit against its contracts
│   ├── cycle/                ← the cycle at runtime: routing, events, status, attestation
│   ├── fleet/                ← many sessions at once, and the line a person watches
│   ├── dist/                 ← into a consumer, and kept in step
│   └── conventions/          ← where things live and what shape they have
├── hooks/           ← what runs in the runtime, outside the agent's turn
│   └── environment/          ← what a hook loads before it runs
├── agents/          ← domain specialists, derived per project (README explains routing)
├── wiki/            ← durable KNOWLEDGE, as an OKF v0.2 bundle
│   ├── sops/                 ← procedures performed on the kit
│   └── decisions/            ← decisions that outlive the discussion
├── records/         ← the TRAIL. What each run left behind, dated and immutable
│   ├── audits/ reviews/ releases/ acceptance/ implementations/
│   └── cycle-events.jsonl    ← one line per phase transition
├── study-material/  ← third-party docs the project depends on. Read-only, not ours
├── session-state/   ← per-session checkpoints. Ephemeral, never evidence
└── tests/           ← the proof the above works; per-slice suites live in skills/*/tests
```

**`wiki/` and `records/` are the same split, twice.** Knowledge evolves, has an
owner and goes stale; a record of one execution on one day does none of those,
and re-verifying it would falsify what it is. That is why they are two
directories and not one — and why `records/` is no longer called
`knowledge-base/`, a name that came to mean *everything left after the knowledge
moved out*. The reasoning is a concept in the bundle:
[`wiki/decisions/where-knowledge-lives.md`](wiki/decisions/where-knowledge-lives.md).

Rules are the contract; a SKILL.md carries only phase-specific detail and points back at its rule.

## Advisory skills

Beyond the pipeline phases, the bundle ships skills that answer architecture questions rather than driving a cycle. They are auxiliary — bound to no `cycle-*.md`, invoked on demand:

| Skill | Answers |
|---|---|
| `arch-check` | Whether a repo has architecture boundaries, whether they can still fire, and which ones it already obeys |

Each refuses the shortcut its field is prone to — classifying a product as CP or AP without its configuration, recommending an unbounded buffer, or retrying a non-idempotent operation without protection.

## Unbreakable principles

- **Evidence is ours or it is not evidence.** Gate G5 at intake, and the Evidence corner downstream.
- **A pointer resolves, line included.** Otherwise the artifact is INVALID.
- **Killing an item is success.** The cycle can say no, with a `kill_reason` naming what was measured.
- **`unknown` is a complete answer** — for the constraint corner, and only there. We do not instrument flow, so demanding a constraint claim would be answered by assertion.
- **Ids are never reused or renumbered.** A killed `B-007` stays `B-007` forever; the number is the audit trail.
- **Measuring is reading.** Discover produces a document, never a patch.
- **Verdicts are derived from findings**, never asserted.

## Relationship to Cycle

Squad is derived from Cycle (MIT) and inverts its centre. Cycle is greenfield and stack-agnostic: its DISCOVER studies **how other projects solved a problem** and explicitly forbids looking at your own code. That is the right question when building something new and the wrong one when maintaining something that runs — it produces imitation, not maintenance.

| | Cycle | Squad |
|---|---|---|
| Driver | a milestone in `ROADMAP.md` | an item in `BACKLOG.md` |
| Discover asks | how did project X solve this? | what is true about *our* system? |
| Terminal artifact | blueprint (a design to copy) | opportunity (a measured gap) |
| Agents | generic, stack-agnostic | 8 specialists with verified build commands |
| Ends when | every milestone is `[x]` | never — maintenance is continuous |

What Squad keeps: TDD halt-loops, the wiring triad, hard gates with derived verdicts, the orthogonal Codex jury, git-safety hooks, and an auditable `records/`.

## Status

Alpha. The pipeline and its gates are implemented and covered by tests; no item has yet run end to end through this version. Everything above describes what the code does, not accumulated production evidence.

## License

MIT — see [LICENSE](LICENSE).
