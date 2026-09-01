# Shared skill rules

Rules the **kit** owns and **two or more skills** read. Not a skill — there is no
`SKILL.md` here, and every enumerator in the kit finds skills by that file, so
this directory is invisible to all of them.

| File | Read by |
|---|---|
| `alignment-threshold.md` | `plan-alignment`, `plan-confidence`, `implement`, `idea-to-release`, `pipeline` |
| `discover-plan-golden-rule.md` | `discover-plan-confidence`, `review` |
| `parallelism-shapes.md` | `pipeline`, `review` |
| `prompt-text-is-not-behaviour.md` | `pipeline`, `review`, `skill-creator` |
| `audit-trail-rotation.md` | `plan-confidence`, `plan-write` |
| `review-model-routing.txt` | `review`, `pipeline` |

## Why here and not in `rules/`

`rules/` is where a **project's own configuration** lives — the routing table, the
enabled languages, the live target, the thresholds, the allow-lists. It has to be
there because `install.sh` does:

```
rm -rf <target>/.claude/skills/ ; cp -r source     ← skills are replaced whole
rules/ and agents/ are snapshotted and preserved   ← the project's edits survive
```

That asymmetry is the whole placement rule. A file the consumer tunes must live in
`rules/`, or the next update destroys it silently — measured before the installer
gained its backup: a `typescript | ENABLED` line and a live-target block added to
a fresh install were both gone after one re-run, with no message.

The six files here are the opposite case. **The kit owns them, no consumer edits
them, and being replaced on every update is correct** — that is how a fix reaches
the eight projects that installed it. Keeping them in `rules/` meant a consumer's
preserved directory carried kit content it had no business owning, and the pointer
the inject hook shows on every turn counted them among the files a reader was told
to consider.

## What did NOT move, and why

- **`rules/cycle-*.md`** — four root checkers glob exactly that pattern:
  `check_xrefs`, `check_phase_numbering`, `check_gate_mechanisms`,
  `check_orphan_verdicts`. Splitting them across skills would end the sweeps that
  prove the chain coherent.
- **Anything a project tunes** — every `*-thresholds.txt`, `*-allowlist.txt`,
  `*-languages.txt`, `live-target.txt`, `acceptance-target.txt`, and the golden
  rules whose `§ 1` is marked PER-PROJECT. Those are the files the installer's
  backup exists for.
- **`sop-schema.md`, `reference-provenance.md`, `auxiliary-skills.txt`,
  `domain-routing.txt`** — read or mechanised from `scripts/` at the root. A rule
  whose mechanism is kit-wide is not skill-shared.
- **The eight doctrine files the inject hook names** — `architecture`, `testing`,
  `error-handling`, `parsimony-ladder`, `git-safety`, `records-location`,
  `autonomy-envelope`, `loop-engine-convention`. They are what the model is
  pointed at before an architectural decision, and that pointer resolves in
  `rules/`.

## Adding a file here

Three conditions, all of them:

1. **The kit owns it** — no consumer edits it, and being overwritten on update is
   the correct behaviour rather than data loss.
2. **Two or more skills read it.** One reader belongs inside that skill.
3. **No root script or hook reads it.** A kit-wide mechanism keeps its rule in
   `rules/`.

Fail any one and the file belongs somewhere else. The failure mode this guards
against is a project's tuning landing in a directory that gets deleted, which is
silent, permanent for anyone who does not version `.claude/`, and looks exactly
like the setting never having been made.
