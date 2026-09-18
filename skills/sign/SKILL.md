---
name: sign
version: 0.1.0
requires: []
description: Put a person's signature on a document that is waiting for one — an alignment brief, the product documents, anything with a `## Sign-off` section. Use this when a scorer returned AWAITING_REVIEW, when `/brainstorm-pieces` computed 90% and stopped, or when someone asks what is waiting on them. Shows what is being signed and writes nothing until a second, deliberate command; refuses to re-sign, and refuses an author signing their own work unless they declare it, which it records in the document rather than silencing.
user-invocable: true
allowed-tools: Read Glob Grep Bash
argument-hint: "[document-path] | --list | --all"
---

# `/sign` — the one act a machine may not perform

Four points in the chain stop until a person signs, and until this existed a person had
no tool for it.

`alignment_judge.py` can sign an item's brief: it writes
`<!-- signed-by: judge/alignment-judge -->` and appends a note saying a judge signature
is worth less than a human one. `score_product_alignment.py` states its own limit in
its own words — *"It can compute the 90%; it cannot supply the signature, and there is
no flag that makes it."*

Both refusals are correct. The consequence was that **the only act reserved for a
person was also the only one with no mechanism**: open the markdown, find the section,
change `[ ]` to `[x]` in the right place, and add an HTML comment whose syntax lives in
a regex inside someone else's script.

## Cycle contract

None. This skill is a phase of no cycle — it is what a person runs when a cycle stopped
and named them. It is declared in `check_xrefs.py`'s `AUXILIARY_SKILLS` for that reason.

## What is waiting on you

```bash
ECO=$([ -d .claude/skills ] && echo .claude || echo .)
python3 "$ECO/skills/sign/scripts/sign_document.py" --list
```

Reports every document under the write root with an unticked sign-off box. An empty
listing says **"nothing is waiting"**, not "everything is signed" — the two are
different facts and the output distinguishes them.

## Signing

```bash
python3 "$ECO/skills/sign/scripts/sign_document.py" <path> --as paulo             # preview
python3 "$ECO/skills/sign/scripts/sign_document.py" <path> --as paulo --confirm   # sign
```

**The default run prints and writes nothing.** A tool that makes signing frictionless
turns a signature into a stamp, which is the failure the machine's own refusal exists to
prevent. `--confirm` is a second, deliberate act, and **there is no `--yes`** — adding
one would remove the only thing this contributes over `sed`.

The preview opens with what the document IS — its title, its own section headings, its
length — then the sign-off section verbatim, who git says wrote the file, how many boxes
are unticked, and what your signature does and does not assert.

**Every line of that summary is extracted, never generated.** The title is the document's
`# ` heading, the sections are its `## ` headings, the count is a count. A model-written
description was the other option and is refused on purpose: a summary the reader has to
verify is worse than none, because the signature already asserts that they read the
document. `tests/test_a_preview_says_what_the_document_is.py` fails on any word in the
summary that is not in the file.

This does not replace reading the document, and the SOP still says so. It makes the
preview name which document — four product documents waiting at once have near-identical
sign-off sections, and before this they were told apart by path alone.

## Signing everything that is waiting

```bash
python3 "$ECO/skills/sign/scripts/sign_document.py" --all --as paulo             # preview all
python3 "$ECO/skills/sign/scripts/sign_document.py" --all --as paulo --confirm   # sign all
```

`--all` takes every document `--list` reports. The four product documents are written
together and read together, and typing the same command four times is friction that buys
nothing.

**It is not a `--yes`, and the distinction is the whole design.** The default run prints
every document's sign-off section — the same preview, in full, one after another — and
writes nothing. What the flag removes is the repetition of the command, not the reading.
A batch mode that skipped the previews would be the flag this skill argues against two
sections above, wearing a different name.

Three behaviours worth knowing before you use it:

| | |
|---|---|
| A refusal stops one document, not the batch | Aborting on the first would leave the earlier ones signed and the later ones untouched, with nothing on screen saying where it stopped. Each refusal is printed against its own path |
| Exit 1 when any document was refused | You asked for *all*. Getting some is not what you asked for, and a `0` would say otherwise |
| `--despite-authorship` applies to every document in the batch | One reason, recorded in each file. If the documents need different reasons, they need different runs |

## What it refuses, and why none of these is an inconvenience

| Refusal | Why |
|---|---|
| `nothing_to_tick` | No unticked box in the `- [ ] …` form every scorer reads. The document is not at that stage |
| `already_signed` | Re-signing hides who signed first. Untick a box to overturn one — which is what the judge's own note tells the operator to do |
| `author_signing_own_work` | The same rule that keeps a judge off a brief it wrote and an author off their own review panel |
| `thin_override_reason` | Under five words. The override preserves a fact; it does not dismiss it |

**Authorship is read from git, never declared.** It is the one refusal that cannot be
self-reported, so it comes from the record. An untracked file has no authors and the
check cannot fire — the preview says `(git could not say)` rather than letting absence
read as a clean bill.

## When you are also the author

On a project with one author the refusal above blocks every signature, which would make
this useless exactly where it is needed. Measured on this kit: **one author across its
entire history.**

```bash
… --as paulo --confirm --despite-authorship "solo project; no second reviewer exists"
```

This does **not** silence the check. It writes into the document that the signer was
also an author, with the reason, and states plainly that the signature is weaker than
one from a reviewer who did not write the document. The next reader sees it. That is the
entire value of a check that can be overridden.

## What a signature means here

**That someone read the document and is willing to say it holds.** Nothing more, and the
written stamp says so: it does not assert that a machine checked anything. The
deterministic score is a separate claim, computed by a separate mechanism, and this tool
neither reads it nor stands in for it.

## What it does NOT do

- **It does not decide what to sign.** `--list` reports; the choice is yours. `--all`
  takes that same list — it does not widen it, and it does not search anywhere `--list`
  would not look.
- **It does not verify the document is true.** Nothing can. It records who is willing to
  say so, which is why the signature has to be a person's.
- **It does not run the scorer.** After signing, run the gate that governs the document
  to see the verdict move. This writes a signature; it computes nothing.
- **It does not sign the review panel's votes.** Those are collected by
  `convene_panel.py` and recorded per reviewer — a different mechanism with a different
  shape.

## Anti-patterns

- **Signing without reading.** The preview exists for one reason; skipping past it makes
  the signature worth what a `sed` would be worth. `--all` prints every preview for
  exactly this reason — scrolling past four of them is the same anti-pattern performed
  faster, and the tool cannot tell the difference.
- **Using `--despite-authorship` as the default.** It is for the case where no second
  reviewer exists, not for the case where finding one is inconvenient.
- **Reading a signature as a pass.** A signed document below the score floor is a signed
  document below the floor; the gate still refuses it, and correctly.
- **Signing on someone else's behalf.** `--as` names who is signing, and that name goes
  in the file next to what they signed.

## Related

- Who may sign an item's brief: [`skills/plan-alignment/SKILL.md`](../plan-alignment/SKILL.md)
- Why a judge may not sign the product: [`skills/brainstorm-pieces/SKILL.md`](../brainstorm-pieces/SKILL.md)
- The threshold and the amendment: [`skills/_kit-rules/alignment-threshold.md`](../_kit-rules/alignment-threshold.md)
- The panel's own signatures: [`rules/review-panel.txt`](../../rules/review-panel.txt)
