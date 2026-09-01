# Operating procedures

What this kit does repeatedly, written down so the next person does not have to
reconstruct it from a script header.

- [Port a fix between the Squad and the Cycle](/sops/port-fix-between-kits.md) —
  measure the receiving kit first, adapt what encodes its contract, and never
  name a mechanism the receiving kit does not have.
- [Install the kit into a consumer](/sops/install-the-kit-into-a-consumer.md) —
  and the two states an install reports as success while being broken.
- [Patch an existing install](/sops/patch-an-existing-install.md) — copy the
  manifest and nothing else, so what the consumer's own cycles generated survives.
- [Propagate a delta across consumers](/sops/propagate-a-delta-across-consumers.md)
  — classify before copying, and never merge a local improvement automatically.

## What these four are worth, stated

One of them was written from runs somebody performed and recorded. The other
three were **derived from the scripts**, and carry `status: draft` for that
reason: the steps are read from code that works, but nobody has followed the
document and confirmed it is followable.

That is a weaker claim, and it is made on purpose. The alternative was leaving
three procedures living in a header comment where nothing verifies them, which is
what this index reported as a gap until 2026-08-31. A draft that says it is a
draft can be corrected by the first person who runs it; a header comment cannot,
because nobody knows it was supposed to be a procedure.
