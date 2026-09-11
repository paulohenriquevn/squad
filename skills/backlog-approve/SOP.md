---
type: SOP
title: Decide which backlog items are the work you want done
description: Render the registry as one readable page, check what each item claims against the files it cites, tick what you commit to, sign, and record the decision as `approved`.
tags: [procedure, backlog, sign-off, governance]

# The OPERATOR's procedure. `SKILL.md` is the contract the agent executes; this is what
# a person needs in order to decide, and to know what their signature claims.
# Derived from the documents in `sources` — no step here was invented.
generated:
  by: claude/opus-5
  at: 2026-09-11
status: stable
sources:
  - id: contract
    resource: ./SKILL.md
  - id: status-flow
    resource: ../../rules/cycle-backlog.md
  - id: signature
    resource: ../sign/SKILL.md
  - id: writer
    resource: ../../mechanisms/cycle/backlog_status.py
---

# Before you invoke

| Check | Why |
|---|---|
| The registry has items at `triaged` | `raw` has not been measured yet; approving it commits to a hypothesis |
| You are not the only reader | The signature is worth what the reading was worth |
| You can spare the reading time | 28 items is roughly 20 minutes. Signing without that produces the formality this exists to replace |

# The procedure

1. **Render.** `build_approval_brief.py <project>` writes one page under the records
   root and prints where. It reads the registry and writes nothing to it.
2. **Read the evidence column first.** Anything marked *does not check out* cites a file
   that is not on disk. That does not make the item wrong — the file may have moved —
   but it means the reason you are being asked to trust cannot currently be followed.
3. **Tick what you want done.** Leave the rest. An unticked item stays exactly where it
   was; nothing is rejected and nothing is killed.
4. **Sign.** `/sign <brief>`. The signature covers what you ticked.
5. **Record.** `apply_approval.py <project> <brief>` moves the ticked items to
   `approved`. Add `--dry-run` first if you want to see the moves before they happen.

# What comes back

| Outcome | Means | Obliges |
|---|---|---|
| `moved N item(s) to approved` | the decision is recorded and those items may now be planned | nothing — the cycle can proceed |
| `REFUSED: the brief is not signed` | ticks exist, a signature does not | sign, or discard the ticks |
| `REFUSED: signed and nothing is ticked` | almost certainly a slip | tick, or accept the backlog unchanged |
| `refused by backlog_status.py` | the item was not at a status this move is legal from | read the reason; the item may already be past this gate |
| `NOT MEASURED` | no brief, no registry, or no writer found | fix the path — nothing was examined |

# What your signature claims, and what it does not

It claims the ticked items are the work you want done, and that the unticked ones are
deliberately not committed to yet.

It does not claim the items are well formed — `check_backlog_structure.py` checked that
— nor that the evidence is sufficient, nor that the work will succeed. `approved` means
somebody decided, and after it `kill_reason` must name who reversed the decision and
what changed. Before approval, killing an item is the cycle working; after it, killing
is a reversal that has to be explained.
