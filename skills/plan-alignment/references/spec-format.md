# The walkthrough spec

The whole authoring surface. No coordinates, no curves, no lanes — those are the
generator's problem, and `layout-engines.md` says why they must not be yours.

```bash
python3 scripts/build_walkthrough.py my-flow.yaml -o my-flow.html
python3 scripts/build_walkthrough.py my-flow.yaml --check      # validate only
```

## Shape

```yaml
title: The alignment gate
subtitle: >-
  One or two sentences. Say what a reader should WATCH for, not what the
  diagram contains.
direction: LR            # LR (default) · TB · RL · BT

nodes:
  agent:  { label: Agent,           kind: service }
  brief:  { label: Alignment brief, kind: store }

flows:
  "Aligned [primary]":
    - from: agent
      to: brief
      label: write brief                    # REQUIRED — the edge's name
      payload: 17 sections · sign-off UNTICKED
      note: >-
        What a reader would get WRONG here.
```

## `kind`

Sets the node's colour and its subtitle. One of `actor`, `service`, `store`,
`external` — the generator refuses anything else, because a kind nobody defined
is a colour nobody can read.

| `kind` | Use for |
|---|---|
| `actor` | A human, or a system outside your control that initiates |
| `service` | Something you run and can change |
| `store` | State that survives the request: a database, a queue, a file |
| `external` | A third party you call and cannot change |

## Flow names carry a scenario class

Tag every flow with one of the four classes. `score_alignment.py` counts them, and
a brief with only `[primary]` scores 0 on `scenario_classes`.

| Tag | The question it answers |
|---|---|
| `[primary]` | What happens when everything works |
| `[alternate]` | The legitimate other route — empty result, cache hit, second tier |
| `[exception]` | A step fails: timeout, rejection, malformed input |
| `[recovery]` | The system comes back: retry, resume, rollback, reconciliation |

The defects live in the three classes nobody draws. `--check` prints a note naming
the missing ones and still builds — refusing would stop an author mid-draft, which
is exactly when the missing classes are still being discovered.

## `note` is the point of the file

The diagram shows what happens. The note says **what people assume instead**.

> ✅ "100% and still not aligned. Readers expect this arrow to reach /plan-write. It
> does not — the number the agent controls was never the gate."
>
> ❌ "The scorer returns the verdict to the agent."

The second one restates the arrow. A walkthrough whose notes only restate their
arrows has drawn the system without surfacing a single disagreement, and has not
earned the time it takes to watch.

Leave `note` out when a step genuinely has nothing anyone would get wrong. An
empty note renders as nothing; a filler note trains the reader to skip them all.

## What the generator refuses

Every problem is reported at once, by name, with an exit code of 1:

- a `from` or `to` naming something that is not a node
- a node with no `label`, or a `kind` outside the four
- a step with no `label` — an unnamed edge is a line nobody can point at
- a flow with no steps, or a spec with no flows or no nodes

## What it warns about and builds anyway

- fewer than four scenario classes across the flows

## Reading the output

The generated HTML is **self-contained**: no build step, no dependencies, no
network beyond Google Fonts, which is the one host the artifact CSP allows. It is
also a **generated file** — edit the YAML and rebuild. Hand-edits are lost, and
the header says so.
