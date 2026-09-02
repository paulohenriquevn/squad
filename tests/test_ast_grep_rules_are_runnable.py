"""The shipped `ast-grep` rule files, checked as artifacts rather than as prose.

`skills/ast-grep` ships five YAML rules and no code, so nothing had ever loaded
them. Two things can be wrong with such a file in a way no reader notices:

  - it does not parse, and every `ast-grep scan` against it reports zero findings
    that were never looked for;
  - its `message` names a metavariable the `rule` does not bind. `ast-grep`
    interpolates metavariables into the message at render time, so an unbound one
    is substituted with nothing and the operator reads a sentence with a hole in
    it. `method-call-ts.yml` shipped "Default $METHOD is `embed`", which rendered
    as "Default  is `embed`" — an instruction pointing at a knob that is not
    there.

Both are checked here because the skill has no test infrastructure of its own and
these are properties of the files, not of a run.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_RULES = sorted((Path(__file__).resolve().parents[1] / "skills" / "ast-grep" / "rules").glob("*.yml"))
_METAVAR = re.compile(r"\$[A-Z_]+")


def test_the_rule_directory_is_not_empty() -> None:
    """A glob that silently matches nothing would make every test below vacuous."""
    assert _RULES, "no rule files found — the tests below would pass on an empty set"


@pytest.mark.parametrize("path", _RULES, ids=lambda p: p.name)
def test_every_rule_parses_and_declares_what_it_needs(path: Path) -> None:
    rule = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert rule.get("id") == path.stem, "the id must match the filename it is cited by"
    assert rule.get("language"), "a rule with no language matches nothing, quietly"
    assert rule.get("rule"), "a rule with no `rule:` block is a message with no query"


@pytest.mark.parametrize("path", _RULES, ids=lambda p: p.name)
def test_no_message_names_a_metavariable_the_rule_does_not_bind(path: Path) -> None:
    """An unbound metavariable renders as nothing, leaving a hole in the sentence.

    A metavariable the pattern DOES bind is fine and useful — `class-extends-ts`
    prints `$BASE`, which renders the matched base class. The defect is only the
    orphan.
    """
    rule = yaml.safe_load(path.read_text(encoding="utf-8"))
    in_message = set(_METAVAR.findall(rule.get("message", "")))
    in_rule = set(_METAVAR.findall(str(rule.get("rule", ""))))

    assert in_message <= in_rule, (
        f"{sorted(in_message - in_rule)} appear in the message but are bound by "
        f"nothing in the rule; ast-grep will render them as empty"
    )
