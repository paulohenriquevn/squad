"""The applier edits a project's maintenance record. These pin what it may not do."""
import sys
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("body,fragment", [
    ('[{"decision": "x", "rationale": "y"}]', "not an object"),
    ('{"B-1": "just a string"}', "not an object with"),
    ('{"B-1": {"decision": "keep it"}}', "`rationale`"),
    ('{"B-1": {"decision": "", "rationale": "y"}}', "`decision`"),
    ('{not json at all', "not valid JSON"),
])
def test_a_decisions_file_of_the_wrong_shape_is_refused_by_name(
        body: str, fragment: str, tmp_path, capsys) -> None:
    """`json.loads` accepts any JSON; `plan()` and `apply()` then index it.

    A file that is a list, or an object whose entry is missing `rationale`, left this
    tool as a TypeError or KeyError traceback. A hand-written decisions file getting one
    key wrong is the ordinary case, and a traceback is the worst way to say so.
    """
    import apply_delegated_decisions as add

    registry = tmp_path / "BACKLOG.md"
    registry.write_text("## B-1\n\nstatus: planned\n", encoding="utf-8")
    decisions = tmp_path / "decisions.json"
    decisions.write_text(body, encoding="utf-8")

    import sys as _sys

    argv = _sys.argv
    _sys.argv = ["apply_delegated_decisions.py", "--registry", str(registry),
                 "--decisions", str(decisions)]
    try:
        code = add.main()
    finally:
        _sys.argv = argv

    assert code == 2
    assert fragment in capsys.readouterr().err
