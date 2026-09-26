"""A doctrine menu goes to a typed decision model before it goes to a headless agent.

The agent path parses free text and costs about USD 1.30 a consultation; a typed
`choice` over the envelope's own sections and the menu's own numbers cannot name a
rule the envelope lacks or an option the menu lacks, and costs a fraction of a cent.
It is trusted only above a confidence floor, never for a rule that needs text typed,
and never across the floor — everything else falls back to the agent, unchanged.
"""
from __future__ import annotations

from pathlib import Path

from decision_model import ChoiceAnswer, DecisionModelUnavailable
from squad_lead import Lead

_MENU = ("Which scope should the chain implement?\n"
         "\n"
         "❯ 1. Gate plus fix on the 8 routes (Recommended)\n"
         "  2. Gate only, separate items\n")

_SCOPE_RULE = "Scope grew during measurement"


class _FakeModel:
    def __init__(self, rule: str = _SCOPE_RULE, option: str = "2",
                 rule_confidence: float = 0.97, option_confidence: float = 0.95,
                 error: str = "") -> None:
        self.rule, self.option = rule, option
        self.rule_confidence, self.option_confidence = rule_confidence, option_confidence
        self.error = error
        self.asked: list[tuple[dict, dict]] = []

    def choices(self, state: dict, questions: dict) -> dict:
        self.asked.append((state, questions))
        if self.error:
            raise DecisionModelUnavailable(self.error)
        return {
            "rule": ChoiceAnswer(self.rule, self.rule_confidence, {}),
            "option": ChoiceAnswer(self.option, self.option_confidence, {}),
        }


def _lead(tmp_path: Path, model: _FakeModel | None, agent_answer=None) -> tuple[Lead, list]:
    asked: list = []
    lead = Lead(session="s", project=tmp_path, agents_when_stuck=True, decision_model=model)
    lead.ask_agent = lambda a, q: asked.append(q) or (agent_answer or (None, "agent stub"))
    return lead, asked


def test_a_confident_answer_chooses_the_option_without_asking_the_agent(tmp_path: Path) -> None:
    lead, asked = _lead(tmp_path, _FakeModel())
    decision = lead.decide(_MENU, idle=200)
    assert decision.action == "choose"
    assert decision.option_number == "2"
    assert _SCOPE_RULE in decision.reason
    assert asked == []


def test_the_questions_offer_exactly_the_envelope_sections_and_the_menu_numbers(
        tmp_path: Path) -> None:
    model = _FakeModel()
    lead, _ = _lead(tmp_path, model)
    lead.decide(_MENU, idle=200)
    _, questions = model.asked[0]
    assert set(questions["option"]["criteria"]) == {"1", "2"}
    rules = set(questions["rule"]["criteria"])
    assert _SCOPE_RULE in rules
    assert "Nothing here fits" in rules
    assert "The floor — what the system never crosses" not in rules


def test_an_answer_below_the_confidence_floor_goes_to_the_agent(tmp_path: Path) -> None:
    lead, asked = _lead(tmp_path, _FakeModel(option_confidence=0.89),
                        agent_answer=(f"OPTION: 1\nRULE APPLIED: {_SCOPE_RULE}", "answered"))
    decision = lead.decide(_MENU, idle=200)
    assert len(asked) == 1
    assert decision.action == "choose"
    assert decision.option_number == "1"


def test_a_rule_that_needs_text_typed_goes_to_the_agent(tmp_path: Path) -> None:
    lead, asked = _lead(tmp_path, _FakeModel(rule="Nothing here fits"))
    decision = lead.decide(_MENU, idle=200)
    assert len(asked) == 1
    assert decision.action == "escalate"


def test_an_unavailable_model_goes_to_the_agent_and_the_log_says_why(tmp_path: Path) -> None:
    lead, asked = _lead(tmp_path, _FakeModel(error="HTTP 402: Insufficient credits"))
    decision = lead.decide(_MENU, idle=200)
    assert len(asked) == 1
    assert decision.action == "escalate"
    assert "402" in decision.reason


def test_without_a_model_the_agent_decides_as_before(tmp_path: Path) -> None:
    lead, asked = _lead(tmp_path, None,
                        agent_answer=(f"OPTION: 2\nRULE APPLIED: {_SCOPE_RULE}", "answered"))
    decision = lead.decide(_MENU, idle=200)
    assert len(asked) == 1
    assert decision.option_number == "2"


def test_an_option_that_opens_a_field_is_not_chosen_by_the_model(tmp_path: Path) -> None:
    menu = ("Which scope should the chain implement?\n"
            "❯ 1. Gate only, separate items\n"
            "  2. Type something\n")
    lead, asked = _lead(tmp_path, _FakeModel(option="2"))
    decision = lead.decide(menu, idle=200)
    assert len(asked) == 1
    assert decision.action == "escalate"


def test_the_floor_never_reaches_the_model(tmp_path: Path) -> None:
    menu = ("❯ 1. Run with --allow-dirty-tree (Recommended)\n"
            "  2. Stop\n")
    model = _FakeModel(option="1")
    lead, _ = _lead(tmp_path, model)
    assert lead.decide(menu, idle=200).action == "escalate"
    assert model.asked == []


def test_an_envelope_that_no_longer_names_the_text_rules_keeps_the_model_out(
        tmp_path: Path) -> None:
    """The two sections the model cannot act on are recognised by name. If the envelope
    renames them, acting on a match that silently stopped matching would let the model
    pick a rule that needs text — so the model is not asked at all."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "autonomy-envelope.md").write_text(
        "# Envelope\n\n## The doctrine — how the system decides what is its\n\n"
        f"### {_SCOPE_RULE}\n\nFinish the measured scope.\n\n## After\n", encoding="utf-8")
    model = _FakeModel()
    lead, asked = _lead(tmp_path, model)
    lead.decide(_MENU, idle=200)
    assert model.asked == []
    assert len(asked) == 1


def test_the_model_reads_the_screen_that_explains_the_menu(tmp_path: Path) -> None:
    """A menu alone rarely says which rule applies; the lines above it do. Measured on
    2026-09-25 with the real envelope: the rule's confidence rose from 0.52 to 0.97 on
    the same scope menu once the screen was in the state, and from 0.77 to 0.90 on a
    loop that ran out of attempts."""
    model = _FakeModel()
    lead, _ = _lead(tmp_path, model)
    lead.decide(_MENU, idle=200)
    state, _ = model.asked[0]
    assert "Which scope should the chain implement?" in state["screen"]
