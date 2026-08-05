---
name: backlog-item
version: 0.1.0
requires: []
description: 'Register one unit of maintenance work against the Theo ecosystem as the next B<N+1> item in BACKLOG.md — cheaply, and before anyone has measured anything. Reads the existing backlog, detects the next free id, runs a mandatory dedup search, routes the item to one of the 8 registered domains, runs a 4-question focused grill (what/why-now, domain+repo, suggested mode, Definition of Done), enforces the no-prior-art gate (an item justified by "project X does it this way" is rejected), and appends one `## B<N+1> — [ ]` block plus a CHANGELOG entry. Phase 0 of the Squad chain: the item it produces is a HYPOTHESIS with evidence:none-yet, which /discover then proves or kills. Refuses if BACKLOG.md does not exist.'
user-invocable: true
allowed-tools: Read Glob Grep Bash Write Edit AskUserQuestion
argument-hint: "{item-slug}"
---

# `/backlog-item` — Register one unit of maintenance work

Take a one-line description of something to improve, fix, verify, or evolve in the Theo ecosystem (e.g. *"trace explorer do theo-lens parece lento"*) and append it as the next `B<N+1>` item in `BACKLOG.md`, with domain routing, a suggested discover mode, and a verifiable Definition of Done.

The item this skill produces is **a hypothesis, not a commitment**. It carries `evidence: none-yet` by design. Proving it — or killing it — is `/discover`'s job.

## Cycle contract

This skill is **phase 0** of [`cycle-backlog`](../../rules/cycle-backlog.md). The cycle rule is the **source of truth** for:

- The item schema and its field semantics
- Status transitions (`raw → triaged | killed → planned → shipped`)
- The 8 registered domains and their repos
- Hard gates G1–G5, verdicts, anti-patterns, rollback
- The handoff contract to [`cycle-discover`](../../rules/cycle-discover.md)

**Read `cycle-backlog.md` before invoking this skill.** This SKILL.md retains only the intake protocol below.

## When to invoke

Invoke `/backlog-item {item-slug}` when ALL of:

- `BACKLOG.md` exists at the umbrella root.
- There is ONE concrete thing to improve, fix, verify, or evolve.
- It maps to exactly one registered domain.

DO NOT invoke when:

- `BACKLOG.md` does not exist — run `/backlog-init` first. (This skill refuses.)
- A sweep already registered the finding (`source: discover-*`). Grep before filing.
- The work spans two domains — split it into two items.
- You are justifying the work by what another project does. See Step 5.

Unlike its Cycle ancestor `/roadmap-feature`, this skill **does not refuse hotfixes, one-line fixes, or refactors with no user-visible change.** Those are the Squad's core workload, not exceptions routed elsewhere.

## Process

### Step 0 — Pre-flight (MANDATORY, fail-fast)

```bash
# 0.1  BACKLOG.md must exist
test -f BACKLOG.md || { echo "FATAL: BACKLOG.md missing — run /backlog-init first"; exit 1; }

# 0.2  intake log must be writable
mkdir -p knowledge-base/backlog 2>/dev/null
test -w knowledge-base/backlog || { echo "FATAL: knowledge-base/backlog not writable"; exit 1; }

# 0.3  CHANGELOG.md must exist (Unbreakable Rule 6)
test -f CHANGELOG.md || { echo "FATAL: CHANGELOG.md missing"; exit 1; }

# 0.4  BACKLOG.md must parse
python3 -c "
import re, sys
items = re.findall(r'^## (B-\d+) — .*\[(.)\]', open('BACKLOG.md').read(), re.MULTILINE)
print('OK', len(items), 'items found')
"
```

A parse failure is surfaced verbatim so the human fixes the malformed registry before anything is appended. Never repair `BACKLOG.md` silently — a registry that got edited by hand is a signal, not a nuisance.

### Step 1 — Resolve the slug

Take `{item-slug}`. If absent, ask for a one-sentence description and derive a kebab-case slug (*"trace explorer parece lento"* → `theo-lens-trace-explorer-latency`).

Prefix the slug with the repo when the same problem shape recurs across repos (`theo-lens-…`, `theo-rag-…`). The registry spans 21 repos; a bare `latency` slug is unsearchable.

### Step 2 — Dedup search (MANDATORY — gate G2)

```bash
# significant nouns from the description, plus the repo name
grep -in -e "{noun1}" -e "{noun2}" -e "{repo}" BACKLOG.md
```

Then read every `B-NNN` block the grep touched — a keyword hit is a candidate, not a verdict.

- **Open item, same problem** → verdict `ITEM_MERGED`. Do NOT allocate a new id. Append the new context to the existing block's body and record the merge in the intake log. Report which id absorbed it.
- **`killed` item, same problem** → allocate a new id, and add `supersedes: B-NNN` plus what changed since the kill. A hypothesis killed for lack of evidence in April can be legitimately re-filed in August; silently re-filing it without the link is what the gate prevents.
- **`shipped` item, problem is back** → new id with `regression_of: B-NNN`. This is a regression, and naming it as one matters more than the item itself.
- **No hit** → proceed.

Skipping this step is a G2 violation. The single-registry decision only holds if intake actually looks.

### Step 3 — Detect next id

Extract every `## B-(\d+)` from `BACKLOG.md`, take `max(N) + 1`, format as `B-{N:03d}`.

```
Itens existentes: 27 (18 shipped, 4 planned, 3 triaged, 2 killed)
Próximo id livre: B-028
```

Ids are monotonic and never reused — including the ids of killed items. No cap.

### Step 4 — Focused grill (4 questions, ONE per turn)

Same protocol as the Cycle grills: one question per turn, each with a recommended answer and its reasoning, persisted after every answer.

| # | Question | Why it must be answered |
|---|---|---|
| 1 | O que é isso, e **o que mudou no nosso sistema** para trazê-lo agora? | Feeds `why_now` and is the input to gate G5. "O que mudou" is the load-bearing half — an item with no local trigger is either prior-art envy or a hunch too vague to measure. |
| 2 | Qual repo, e portanto qual domínio? | Feeds `domain` + `repo` (G1) and decides which specialist picks it up. Offer the routing table; if the answer names two domains, G3 fires and the item splits. |
| 3 | Qual modo de discover parece certo — review, live-test, bug ou evolve? | Feeds `suggested_mode`. State explicitly to the user that this is **a suggestion DISCOVER may overrule**, so nobody treats their guess as a decision. |
| 4 | Qual é a Definition of Done verificável (1-3 bullets)? | Feeds `dod` (G4). This is the criterion that closes the item. Reject bullets that restate the title or cannot fail. |

**Note what is NOT asked: evidence.** Intake has no evidence gate. If the user offers a `file:line` or a trace id unprompted, record it — but never ask for it, and never let its absence block the item.

#### 4.X — Persistence after every answer (MANDATORY)

Append to `knowledge-base/backlog/{item-slug}-intake.md` after each answered question, with `generated_by: backlog-item`. Set `status: completed` on success at Step 6, `status: aborted` if the user stops early. A grill abandoned mid-way leaves a log, not a half-written registry entry — `BACKLOG.md` is touched only at Step 6.

### Step 5 — No-prior-art check (MANDATORY — gate G5)

Read the Q1 answer. The item is **rejected** if the justification rests on what another project, product, or framework does, rather than on something observable in our system.

| Rejected | Accepted |
|---|---|
| "O LangSmith tem waterfall de traces, a gente devia ter" | "O explorer não mostra a hierarquia de spans, então debugar um agente aninhado exige abrir 6 traces" |
| "Todo mundo usa cache aqui" | "O endpoint faz 4 round-trips ao Postgres por request" |
| "Vi num post que o padrão é X" | "Nosso handler duplica a lógica de auth em 3 lugares e já divergiram uma vez" |

On a hit, use `AskUserQuestion`:

```
A justificativa deste item se apoia em como outro projeto resolve o problema:

  "{trecho}"

O Squad só aceita trabalho justificado por evidência do nosso próprio sistema
(cycle-backlog § Hard gates, G5). Isso não proíbe conhecer a solução dos outros
— proíbe que ela seja a razão.

  [ ] Reformular — existe um motivo local, deixa eu descrevê-lo
  [ ] Registrar assim mesmo — o gate leu errado, a razão já é local
  [ ] Cancelar — não há motivo local; isso não é um item
```

Record the decision (`g5_reformulated` / `g5_false_positive` / `g5_rejected`) in the intake log. The keyword heuristic surfaces the question; the human decides. A false positive is a normal outcome, not a failure of the gate.

### Step 6 — Write

Only after Steps 2–5 pass. Three writes, in this order:

1. **`BACKLOG.md`** — append one `## B-NNN` block per the schema in `cycle-backlog.md § Item schema`, with `status: raw`, `source: human`, `evidence: none-yet`, and the provenance line:
   `> Registrado {{DATE}} por `/backlog-item` (slug: `{{SLUG}}`).`
   Append only. Never reorder, never renumber, never touch another block.
2. **`CHANGELOG.md`** — one line under `[Unreleased] § Added`, attributed to the target repo per the umbrella convention: `**{repo}:** backlog B-NNN — {título} (#NNN)`.
3. **`knowledge-base/backlog/{slug}-intake.md`** — flip the log to `status: completed`.

If the `BACKLOG.md` write fails, do not write the CHANGELOG entry. A changelog line for an item that does not exist is worse than no line.

### Step 7 — Report

```
ITEM_REGISTERED  B-028 — {título}
  domain: {domain} → especialista {domain}
  repo: {repo}
  suggested_mode: {mode}  (sugestão — /discover pode reclassificar)
  evidence: none-yet      (hipótese; /discover mede)
  dod: {n} critérios

Próximo passo:  /discover --mode {mode} B-028
```

For `ITEM_MERGED`, report the absorbing id and what was appended to it. For `ITEM_REJECTED`, report the gate that fired and what would make the item acceptable — a rejection that does not say how to fix it just gets re-filed verbatim tomorrow.

## Anti-patterns

Cycle-level anti-patterns live in `cycle-backlog.md § Anti-patterns`. Specific to this skill:

- **Asking for evidence during the grill.** Turns intake into triage and silences the hunch this phase exists to capture.
- **Writing to `BACKLOG.md` before the grill completes.** An aborted grill must leave the registry untouched.
- **Auto-resolving a dedup hit.** The grep finds candidates; the human confirms whether it is the same problem. A wrong merge buries an item forever.
- **Treating a G5 hit as a refusal to do the work.** The gate rejects a *justification*, never an idea. The correct move is to ask for the local reason, not to close the conversation.
- **Deriving `domain` from the slug.** Route from the repo via the table in `cycle-backlog.md § Domain routing`, not from what the slug sounds like.

## Cross-references

- Cycle rule (source of truth): [`rules/cycle-backlog.md`](../../rules/cycle-backlog.md)
- Downstream: [`rules/cycle-discover.md`](../../rules/cycle-discover.md) — measures the hypothesis, flips `raw → triaged | killed`
- Rule schema: [`rules/cycle-rule-schema.md`](../../rules/cycle-rule-schema.md)
- Branching contract for the registry commit: [`rules/git-safety.md`](../../rules/git-safety.md)
