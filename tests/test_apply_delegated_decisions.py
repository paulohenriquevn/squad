"""The applier edits a project's maintenance record. These pin what it may not do."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "cycle"))

from apply_delegated_decisions import apply, plan

REGISTRY = """# Backlog

## B-165 — An environment lost its edge   [ ]

status: triaged
blocked_by: aguardando decisão binária DoD bala 1: retire standalone-public OU dá borda própria a ele.
severity: baixa

## B-139 — The dashboard serves from someone's house   [ ]

status: triaged
blocked_by: aguardando operador executar migração — requer provisionamento de /opt/theo no host.
severity: alta

## B-060 — Four planes meet in a folder   [ ]

status: triaged
blocked_by: aguardando disposição de status: nenhuma transição canônica encaixa limpa.  # english-only: fixture in the language the classifier reads
severity: media
"""

DECISIONS = {
    "B-165": {"decision": "retire standalone-public", "rationale": "the doc labels it legacy"},
    "B-139": {"decision": "provision the host", "rationale": "irrelevant — must be refused"},
}


def _registry(tmp_path: Path) -> Path:
    p = tmp_path / "BACKLOG.md"
    p.write_text(REGISTRY)
    return p


def test_plan_writes_nothing(tmp_path):
    reg = _registry(tmp_path)
    before = reg.read_text()
    plan(reg, DECISIONS)
    assert reg.read_text() == before


def test_a_retained_wall_is_never_rewritten_even_with_a_decision_supplied(tmp_path):
    """B-139 needs a host. A decision handed to it must not clear its wall."""
    reg = _registry(tmp_path)
    text, changed = apply(reg, DECISIONS)
    assert "B-139" not in changed
    assert "provisionamento de /opt/theo" in text


def test_a_delegable_wall_with_a_decision_is_rewritten(tmp_path):
    reg = _registry(tmp_path)
    text, changed = apply(reg, DECISIONS)
    assert "B-165" in changed
    assert "retire standalone-public" in text
    assert "decided_by" in text


def test_a_delegable_wall_with_no_decision_stays_walled(tmp_path):
    """B-060 is delegable, but nobody decided it. Clearing it would be an unblock
    with nothing behind it — the exact failure this mechanism exists to prevent."""
    reg = _registry(tmp_path)
    text, changed = apply(reg, DECISIONS)
    assert "B-060" not in changed
    assert "disposição de status" in text

    rows = {r["item"]: r for r in plan(reg, DECISIONS)}
    assert rows["B-060"]["action"] == "retain"
    assert "no decision supplied" in rows["B-060"]["note"]


def test_other_items_are_left_byte_identical(tmp_path):
    """A pass that rewrites one item must not perturb the rest of the file."""
    reg = _registry(tmp_path)
    text, _ = apply(reg, DECISIONS)
    for untouched in ("## B-139 — The dashboard serves from someone's house   [ ]",
                      "## B-060 — Four planes meet in a folder   [ ]",
                      "severity: alta"):
        assert untouched in text


def test_every_item_survives_the_pass(tmp_path):
    reg = _registry(tmp_path)
    text, _ = apply(reg, DECISIONS)
    for item in ("B-165", "B-139", "B-060"):
        assert f"## {item}" in text
