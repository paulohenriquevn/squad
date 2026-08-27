---
okf_version: "0.2"
---

# Squad — durable knowledge

The knowledge an agent reads before acting on this kit: the procedures it
performs, the decisions it must not relitigate, and the external material it
depends on.

**This bundle is not the audit trail.** Dated, immutable records of what
happened — audits, reviews, implementations, releases, acceptance runs, SOP run
records — live in `knowledge-base/` and stay there. A record of one execution on
one day is not a concept that evolves, and forcing it into a schema built for
knowledge that does would lose what makes it evidence.

## Directories

- [`sops/`](/sops/index.md) — operating procedures for what this kit does
  repeatedly: installing into a consumer, patching an install, porting a fix
  between kits, cutting a release.
- `decisions/` — architecture decisions that outlive the discussion that
  produced them. *(empty)*
- `references/` — external material absorbed into concepts, with the source URL
  kept as `resource` for re-checking. *(empty)*
- `opportunities/` — measured findings from `/discover-execute` that survived
  their falsification criterion. *(empty)*

## Reading the trust tier

Every concept here carries `generated` (who wrote it) and, when a human has
actually confirmed it, `verified`. A concept with no `verified` is
**unverified** — written by an agent, never checked by a person. That is the
honest default, and inflating it by writing `human:` for agent-authored content
is the one thing that would make this bundle's trust layer meaningless.
