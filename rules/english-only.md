# English only
<!-- rule-id: SQ-LNG-01 -->

**Skill:** every skill · **Mechanised by:** `mechanisms/gates/check_english_only.py`

## The rule

This repository, and every repository that installs this kit, is written in
English. All of it: prose, comments, docstrings, commit messages, test names,
fixtures, identifiers, error strings, `BACKLOG.md`, `ROADMAP.md`, plans, reviews
and records.

Not a style preference. Consumers' agents read these files as instructions, and a
contract written half in one language is a contract whose exact wording nobody
can grep for.

## Why it needed a gate

The policy existed and nothing enforced it. Measured 2026-08-27: **334 Portuguese
markers across 21 versioned files** in this kit, 93 across 17 in the sibling.

Two checkers had gone past tolerating it and were *accepting* it as input:

| Checker | Accepted |
|---|---|
| `check_adr_completeness.py` | `"por que não"`, `"considerada"`, `"considerado"` |  <!-- english-only: the gate must name what it detects -->
| `check_deps_audit.py` | `(nenhuma)` as a valid "no new dependency" declaration |  <!-- english-only: the gate must name what it detects -->

A kit whose gates read a second language has decided its own policy is advisory —
a plan written in Portuguese passed *those* gates while breaking the rule that
governs the repository. Both now read English only.

It also spreads by example. One consumer wrote an entire `BACKLOG.md` in
Portuguese inside an English-by-policy repository, having read four sibling
registries in English and copied none of them, because nothing said no.

## How a line keeps its Portuguese

Some lines must contain Portuguese, and they are exempted **on the line itself**,
with the reason:

```python
plan = _write(tmp_path, "Isso e ruim.\n")  # english-only: fixture must be PT to trip the rule
```

```markdown
*"Escolha sempre o nome mais específico"  <!-- english-only: verbatim quote of CLAUDE.md -->
```

An exemption with no reason after the colon does not count. A silent opt-out is
the thing being prevented, so an opt-out that says nothing is refused exactly
like the Portuguese it was trying to keep.

The three legitimate cases seen so far:

1. **A verbatim quotation** of something written in Portuguese.
2. **A fixture that must be Portuguese** to exercise the rule it tests — the
   PT-BR demonstrative smell cannot be tested in English.
3. **A detector naming what it detects** — `skills/plan-confidence/templates/rubric-v1.md` lists the
   demonstratives it looks for.

Anything else is a translation waiting to happen.

## Hard gates

- **No Portuguese outside a declared exemption** — `mechanisms/gates/check_english_only.py`.
  Runs in CI, and as a `PostToolUse` hook (`hooks/english-only-check.py`) that
  reports on the file just written. The hook is advisory and the checker is the
  verdict: at write time a quotation and a lapse look alike, and blocking the
  author mid-edit fights them at the moment they can least explain themselves.
- **No checker accepts Portuguese input** — _(not mechanized: judgement, by
  decision — a gate scanning every checker for accepted vocabulary would flag the
  three files whose job is to name Portuguese, and the exemption marker cannot
  express "this list is data, not prose")_. The two that did were fixed on
  2026-08-27, and this line is what a reviewer reads before adding a third.

## Detection is precise, not exhaustive

The checker matches function words that cannot plausibly appear in English
technical prose. It deliberately does **not** match `para`, `com`, `de`, `mode`
or `data`: those are English, or live inside identifiers, paths and URLs.

That choice is about where this runs. The gate ships to every consumer, and the
person who meets a false positive there did not write the gate and has no reason
to trust it — the first thing anyone does with a noisy gate is turn it off.
Missing some Portuguese is recoverable. Being ignored is not.

## Anti-patterns

- **Translating a quotation.** If the source is Portuguese, quoting it in English
  makes the quotation false. Exempt it.
- **Adding a term in another language to a checker** so a document passes. That
  is moving the goalpost, and it is how both defects above started.
- **Exempting to silence the gate.** The reason after `english-only:` is read by
  the next person; "fix later" is not a reason.
- **Writing the CHANGELOG in whatever language the day happened in.** Entries are
  for consumers, and consumers read English.

## Cross-references

- Checker: `mechanisms/gates/check_english_only.py`
- Hook: `hooks/english-only-check.py`
- The warn-first split this follows: `hooks/public-copy-lint.py`, `rules/public-copy.md`
