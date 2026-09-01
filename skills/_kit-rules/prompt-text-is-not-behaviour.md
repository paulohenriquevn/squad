# Prompt text is not behaviour

A test that greps shipped prose fails when someone improves the sentence and passes when someone breaks the thing the sentence describes.

## The rule

**Do not pin the WORDING of prose the kit ships.** That includes `SKILL.md`
bodies, `rules/*.md`, role prompts, generated instruction files and
`HOW-TO-USE.md`. Wording is not production behaviour, and `"phrase" in text` is
not a check on it.

Taken verbatim in spirit from [`unclebob/swarm-forge`](https://github.com/unclebob/swarm-forge),
whose entire `AGENTS.md` is four lines saying this. That project reached the
position deliberately; this kit reached it on 2026-08-29 by paying for it —
`test_layout.py` pinned an exemption by grepping `run_validation.py` for the
literal `'project_root / "records" / "plans"'`, and broke when those literals
became a table that resolves a THIRD layout. It failed while the behaviour it
protects got strictly better, which is the defining symptom.

## What is still legitimate

The line is not "reads a file". It is **structure versus wording**:

| Legitimate | Fragile |
|---|---|
| The frontmatter parses and carries `name`, `description` | The description contains the word "measure" |
| A required `## section` is present | That section says "Fail-closed" |
| A declared script path exists on disk | The prose mentions the script by name |
| The generated REPORT contains a finding id | The SKILL.md warns about deleting findings |
| `check_english_only` matching Portuguese markers | — that IS the subject, not a proxy for it |

Structure survives a rewrite. Wording does not, and the rewrite is usually an
improvement.

## The deeper reading, which is the useful one

A test that greps a contract is a **symptom**: it means the guarantee exists
only as prose, and somebody felt the need to guard it. The guard does not work —
a synonym defeats it and an unrelated occurrence satisfies it — so the finding is
not "fix the test". The finding is:

> Mechanise the guarantee, or accept that it is prose and stop pretending a grep
> protects it.

Measured here on 2026-08-29: `test_the_contract_forbids_the_two_dishonest_ways_past_a_blocker`
asserted `"delete" in text` over `skills/review/SKILL.md`. What it was defending
is real — `consolidate_findings.py` scores from OPEN findings, so deleting a
finding or lowering its severity both pass, and only the contract warns against
it. The grep was the wrong instrument for a real problem.

## Enforcement

`scripts/check_prose_tests.py` reports asserts whose left side is a string
literal and whose right side traces back to text read from a shipped prose file
in the same function. It is deliberately precise rather than exhaustive: it
ignores asserts over program output (`result.stdout`, a generated report, a
parsed settings dict), because those are behaviour.

A line may keep its grep by saying why **on the line itself**:

```python
assert "status: CLOSED" in text  # prose-test: the contract IS the subject here
```

An exemption with no reason does not count — a silent opt-out is the thing being
prevented.

## Cross-references

- Checker: `scripts/check_prose_tests.py`
- The defect that paid for this: `CHANGELOG.md`, `test_layout.py` entry of 2026-08-29
- Source of the rule: [`unclebob/swarm-forge`](https://github.com/unclebob/swarm-forge) `AGENTS.md`
