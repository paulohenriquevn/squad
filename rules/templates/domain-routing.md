## Domain routing

`domain` is what assigns an item to a specialist. **This table is DERIVED from
the project it lives in** — nothing here may be copied from another ecosystem,
because it describes which repositories exist in this one.

**It is born empty, and that is deliberate.** The kit used to ship the table of
the ecosystem it was written in: eight domains pointing at twenty repositories the
consumer does not have. The effect was measured on 2026-08-18, on an adopter — 88
items filed with real `file:line` evidence, all refused by gate G1 as
`BLOCKER/unroutable_repo`. The gate was right: it genuinely could not tell who
owned the work. Inheriting the wrong map is worse than having no map, because the
refusal looks like a problem with the item rather than with the configuration.

### Derive a sua

```bash
python3 .claude/skills/backlog-init/scripts/detect_domains.py --root . \
  --write .claude/rules/cycle-backlog.md
```

The script reads the topology from disk — not from an inventory, not from a
`CLAUDE.md` — and fills in the table below. Then write the specialist file it
names, under `.claude/agents/`.

While this section is empty, `/backlog-item` refuses every item. That refusal is
the correct behaviour: with no table, routing would be a guess.

| Domain | Repos (present on disk) | Specialist |
|---|---|---|
| _(empty — run `detect_domains.py --write`)_ | | |

**One repo, one domain.** `scripts/route_domain.py` enforces this invariant:
listing the same repository under two domains makes routing depend on iteration
order, and the same item starts routing differently between runs. When one
repository holds two genuinely distinct things — a service and the dashboard that
consumes it, in the same checkout — separate them by path (`repo` and
`repo/subdir`), never by repeating the bare name in both.

**Record the divergence instead of deleting it.** A repository the inventory
names and disk does not have should stay listed, marked as having no checkout: an
item filed against it routes nowhere, and seeing that written down is cheaper than
discovering it through the refusal.
