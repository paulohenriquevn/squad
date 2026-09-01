---
okf_version: "0.2"
---

# Squad — durable knowledge

The knowledge an agent reads before acting on this kit: the procedures it
performs, the decisions it must not relitigate, and the external material it
depends on.

**This bundle is not the audit trail.** Dated, immutable records of what
happened — audits, reviews, implementations, releases, acceptance runs, SOP run
records — belong to `records/`, which every consumer keeps and this repository
does not carry in its index. A record of one execution on one day is not a
concept that evolves, and forcing it into a schema built for knowledge that does
would lose what makes it evidence. The consequence for this bundle is the whole
reason it exists: what is written here is the half meant to survive the run.

## Directories

- [`sops/`](/sops/index.md) — operating procedures for what this kit does
  repeatedly: installing into a consumer, patching an install, propagating a
  delta across consumers, and porting a fix between the sibling kits. Three of
  the four are `draft`: derived from the scripts, not from a run anyone
  performed and recorded.
- [`decisions/`](/decisions/where-knowledge-lives.md) — architecture decisions
  that outlive the discussion that produced them.
- [`references/`](/references/judgement-gates-are-insurance.md) — external
  material absorbed into concepts, with the source URL kept as `resource` for
  re-checking.
- `opportunities/` — measured findings from `/discover-execute` that survived
  their falsification criterion. *(empty)*

## Reading the trust tier

Every concept here carries `generated` (who wrote it) and, when a human has
actually confirmed it, `verified`. A concept with no `verified` is
**unverified** — written by an agent, never checked by a person. That is the
honest default, and inflating it by writing `human:` for agent-authored content
is the one thing that would make this bundle's trust layer meaningless.
