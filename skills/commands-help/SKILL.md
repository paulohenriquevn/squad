---
name: commands-help
version: 0.1.0
requires: []
description: Show all available Squad commands with descriptions and recommended flows. Use when the user asks for help, wants to know what commands are available, or says "what can you do" / "help" / "list commands".
user-invocable: true
allowed-tools: Read Glob Bash
argument-hint: "(no arguments)"
---

# /commands-help

Display every skill in the Squad ecosystem, organized by cycle, plus the flows that chain them.

## Instructions

When invoked, list `skills/*/SKILL.md` and read each frontmatter `description` so the output
reflects **what is on disk right now**, not what this file remembers. If a skill exists on disk
and is missing from the tables below, say so explicitly — a help command that silently omits a
command is worse than no help command.

Then print the guide.

---

## Squad — Available Commands

### The two registries

Squad has two registries, on two different axes. Confusing them is the most common mistake.

| File | Ids | Answers | Created by |
|---|---|---|---|
| `BACKLOG.md` | `B-NNN` | "what should we look at next?" | `/backlog-init`, then `/backlog-item` |
| `ROADMAP.md` | `M<N>` | "what did we promise a user?" | **hand-authored — no skill generates it** |

Only a milestone has a checkbox, so only a milestone reaches `/acceptance`. A `B-NNN` released
without a milestone ends at `RELEASED`, and that is correct.

### Recommended flows

**A. A hunch worth checking (the default maintenance loop):**
```
/backlog-item {slug}                    register it — no evidence required, on purpose
/discover-plan B-NNN --mode {mode}      what will be measured, and what would kill it
/discover-edge-cases B-NNN              what could make the measurement lie
/discover-plan-confidence B-NNN         is the plan ready to run?
/discover-execute B-NNN                 run it — ITEM_KILLED is a success
/discover-confidence B-NNN              is the finding solid enough to act on?
   → then flow B
```

**B. The measurement holds — build the fix:**
```
/to-plan {slug} → /edge-case-plan → /deps-audit → /plan-confidence
              → /implement → /code-quality → /review → /release → /acceptance
```

**C. Requirements are vague — get grilled first:**
```
/grill-me {topic}  →  then flow B
```

**D. Autonomous, end to end:**
```
/session-goal M2      bind the session so it cannot stop before acceptance is green
/idea-to-release M2       run every phase of flow B for that milestone
```

There is **no `/discover` command** — the discovery chain is six separate skills (five mandatory
plus `/discover-improve`, invoked only on `NEEDS_REVISION`), each with its own gate. When a rule or
a skill refers to the chain as a whole, it names the cycle — `cycle-discover` — never a slash
command. `/idea-to-release` runs them for you; invoke them by hand when you want to stop between gates.

### cycle-backlog — the registry

| Command | Purpose |
|---|---|
| `/backlog-init` | Create `BACKLOG.md` once, at the root of the governed scope. Refuses if it exists |
| `/backlog-item {slug}` | Register one `B-NNN`. Intake requires no evidence — deliberately |
| `/backlog-review [path]` | Report what has rotted in the registry. Read-only |

### cycle-discover — measure before believing

Runs against **our** code and runtime. Prior art can never be evidence here.

| Command | Purpose |
|---|---|
| `/discover-plan B-NNN --mode {review\|live-test\|bug\|evolve}` | Measurement plan + the falsification criterion |
| `/discover-edge-cases {slug}` | What could make the measurement lie |
| `/discover-plan-confidence {slug}` | Score the plan (deterministic, no LLM calls) |
| `/discover-execute {slug}` | Run it. Also `--sweep {domain}` to sweep with no prior item |
| `/discover-confidence {slug}` | Score the opportunity |
| `/discover-improve {slug}` | Lift a low score — improves the argument, never the claim |

### cycle-plan — design the fix

| Command | Purpose |
|---|---|
| `/grill-me {topic}` | Interview one question at a time until requirements are shared |
| `/to-plan {slug}` | Turn the context into an implementation plan |
| `/edge-case-plan {slug}` | Unforeseen edge cases in the plan |
| `/deps-audit [slug]` | CVE + outdated audit across npm/pip/cargo/go. Never edits manifests |
| `/plan-confidence {slug}` | Score the plan (must pass before `/implement`) |
| `/plan-improve {slug}` | Auto-improve a plan below `SHIPPABLE_WITH_CAVEATS` |

### cycle-implement → cycle-release — build and ship

| Command | Purpose |
|---|---|
| `/implement {slug}` | TDD halt-loop + wiring triad + quality gates |
| `/code-quality [slug]` | Dead symbols, fabricated APIs, mutation testing. Read-only |
| `/review {slug}` | Multi-agent parallel review. The most rigorous gate |
| `/release [bump]` | Semver tag + `develop → main` PR. Pauses for human approval |

### cycle-acceptance — did it actually work?

| Command | Purpose |
|---|---|
| `/acceptance M<N>` | Exercise the **released** delivery against the milestone's DoD. Only a green verdict flips `[ ]` → `[x]` |
| `/session-goal M<N> [M<N> ...]` | Bind the session so it cannot stop until acceptance is green |

### Orchestration

| Command | Purpose |
|---|---|
| `/idea-to-release [M<N>\|B-NNN\|{slug}]` | Chain discover → plan → implement → code-quality → review → release → acceptance |

### Independent audits (do not gate the main chain)

| Command | Purpose |
|---|---|
| `/trajectory-review [slug]` | Empirical trajectory validation — benchmarks, complexity, scalability. Opt-in per project |
| `/arch-check [repo]` | Verify architecture boundaries, or propose ones the repo already obeys |
| `/honesty-gate [audit\|log-evidence\|status]` | Honesty gate blocking "production-ready" claims without evidence |

### Setup and utilities

| Command | Purpose |
|---|---|
| `/quality-init TARGET` | Generate quality-gate hooks calibrated to the project's real p90 metrics |
| `/ast-grep {pattern}` | Structural search via tree-sitter — queries Grep cannot express |
| `/skill-creator` | Author, improve and eval any skill |
| `/commands-help` | This help (you are here) |

### Domain specialists

Invoked on demand; not a phase of any cycle.

| Command | Purpose |
|---|---|
| `/cap-theorem-specialist {scenario}` | CP/AP trade-offs. Refuses to classify a product without its configuration |
| `/backpressure-specialist {symptom}` | Producer/consumer rate mismatch. Refuses unbounded buffers |
| `/resilience-specialist {incident}` | Timeouts, retries, breakers, bulkheads. Refuses unbounded retries |

### Presentation and design

| Command | Purpose |
|---|---|
| `/slide-deck {topic}` | Full presentation — orchestrates `/marp-slide` + `/excalidraw` |
| `/marp-slide {topic}` | Marp slides only (`.md` + `.html` + `.pptx`) |
| `/excalidraw {topic}` | Excalidraw diagram JSON that argues visually |
| `/frontend-design` | Visual direction for new UI that does not read as templated |

### Prerequisites

```bash
python3 --version              # 3.10+ required
python3 -c "import yaml"       # PyYAML
ast-grep --version             # structural queries (optional)
```
