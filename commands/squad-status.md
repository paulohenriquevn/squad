---
description: "Show why the maintenance queue is where it is: what the selector would hand out next, which items a phase halted on, what those halts are waiting for, and what the watchdog last decided. Read-only."
disable-model-invocation: true
allowed-tools: "Bash Read"
---

Answer one question — **why is the queue in this state?** — from the four sources that
know, and never from memory of a previous run.

Run these, in order, from the project root:

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)

# 1. What may start now, and everything held back, with the reason for each.
python3 "$ECO/skills/backlog-review/scripts/select_backlog_item.py" BACKLOG.md

# 2. Which halts have a cause the queue can attack, and which need a person.
python3 "$ECO/skills/backlog-review/scripts/squad_boss.py" .

# 3. What the chain declared against what actually ran.
python3 "$ECO/mechanisms/gates/check_phase_drift.py"

# 4. The watchdog's last decisions, if it is running.
tail -5 /tmp/squad-lead.jsonl 2>/dev/null || echo "no watchdog log at /tmp/squad-lead.jsonl"
```

Then say, in this order and nothing more:

1. **What runs next**, and why that item and not an older one.
2. **What is held**, split into the two kinds — an impediment a person declared in the
   registry, and a halt a phase wrote a report for. They need different actions from
   different people, so never merge them into one list.
3. **What needs a person**, named precisely: which decision, on which item, and where
   the report that asks for it lives.

If every source agrees the queue is moving, say so in one line. A long report about a
healthy queue trains the reader to skip the next one.

Read `{slug}-BLOCKED.md` in full before describing a halt. The verdict token says a
gate failed; only the report says what it was waiting for, and the difference between
those two is the whole point of this command.
