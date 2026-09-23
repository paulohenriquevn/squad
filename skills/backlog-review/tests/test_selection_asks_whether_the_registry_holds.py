"""The selector does not hand out work from a registry its own gate calls INVALID.
`check_backlog_structure.py` and `select_backlog_item.py` read the same file with
the same parser — the selector imports `_parse_items`, `Item` and three helpers
from the checker. It imports no verdict. So the two disagree in the one direction
that matters: the gate refuses the file and the selector serves from it.
Measured 2026-09-19 on a registry holding `B-001` twice:
    check_backlog_structure  rc=1  INVALID
      BLOCKER duplicate_id: `B-001` appears twice (lines 5 and 17). Ids are the
      audit trail; two blocks sharing one destroys it.
    select_backlog_item      ITEM_SELECTED  ->  B-001
      queue: ['B-001', 'B-001']
Nothing in the selector's output names the structure. The caller receives an id
that identifies two different blocks and cannot tell which one it was handed, and
the queue would run the same id twice.
WHERE THE LINE IS, and it is not "any finding". `INVALID` means an id does not
resolve or resolves to two things — the selector's own ANSWER becomes ambiguous,
so it has nothing honest to return. `NEEDS_REVISION` means the content is weak,
which is the condition the pipeline exists to improve; refusing to select on it
would stop the machine over exactly the work it is built to do, and a gate that
blocks that is a gate people route around. A consumer measured the same day sat
at 11 `status_contradicts_body` majors — every one of them real, none of them a
reason to stop handing out work.
`BACKLOG_INVALID` rather than reusing `BACKLOG_BLOCKED`: blocked means impediments
hold every candidate, which is a different fact with a different remedy, and one
outcome for two facts is what this kit keeps paying to undo.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "skills" / "backlog-review" / "scripts"
_SELECT = _SCRIPTS / "select_backlog_item.py"
_CHECK = _SCRIPTS / "check_backlog_structure.py"
_BLOCK = """
## {iid} — {title}   [ ]
domain: data-plane
repo: web-console
suggested_mode: review
source: human
evidence: {evidence}
why_now: the dashboard loads 30d by default
status: {status}
dod:
  - p95 under 800ms
"""
def _registry(tmp_path: Path, *blocks: str) -> Path:
    path = tmp_path / "BACKLOG.md"
    path.write_text("# Backlog\n\n## Items\n" + "".join(blocks), encoding="utf-8")
    return path
def _block(iid: str, *, title: str = "Reduce round-trips", status: str = "triaged",
           evidence: str = "src/trace/list.py:31 — 4 round-trips per row") -> str:
    return _BLOCK.format(iid=iid, title=title, status=status, evidence=evidence)
def _select(path: Path) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(_SELECT), str(path), "--json"],
                          capture_output=True, text=True, check=False)
    return proc.returncode, json.loads(proc.stdout)
def _structure_rc(path: Path) -> int:
    return subprocess.run([sys.executable, str(_CHECK), str(path)],
                          capture_output=True, text=True, check=False).returncode
def test_a_registry_the_gate_calls_invalid_yields_no_item(tmp_path: Path) -> None:
    path = _registry(tmp_path,
                     _block("B-001"),
                     _block("B-001", title="A duplicate id", evidence="src/other.py:10 — else"))
    assert _structure_rc(path) == 1, "the fixture stopped being INVALID; this proves nothing"
    code, out = _select(path)
    assert out["verdict"] == "BACKLOG_INVALID", out["verdict"]
    assert out["item_id"] is None, out["item_id"]
    assert code != 0, code
def test_the_refusal_names_the_blockers_rather_than_the_count(tmp_path: Path) -> None:
    """"1 blocker" sends a person to run another command to find out which."""
    path = _registry(tmp_path,
                     _block("B-001"),
                     _block("B-001", title="A duplicate id", evidence="src/other.py:10 — else"))
    _, out = _select(path)
    assert "duplicate_id" in out["reason"], out["reason"]
    assert "B-001" in out["reason"], out["reason"]
def test_a_weak_but_structurally_sound_registry_still_selects(tmp_path: Path) -> None:
    """The line, pinned from the other side.
    A registry with major findings and no blocker is exactly what the pipeline
    exists to improve. Refusing here would stop the machine over its own purpose.
    """
    path = _registry(tmp_path, _block("B-001"))
    assert _structure_rc(path) in (0, 3), "fixture should be sound or merely weak"
    _, out = _select(path)
    assert out["verdict"] == "ITEM_SELECTED", out
    assert out["item_id"] == "B-001"
def test_an_unreadable_registry_is_not_reported_as_empty(tmp_path: Path) -> None:
    """Cannot read is not nothing to do, and the two send a person to opposite places."""
    path = tmp_path / "BACKLOG.md"
    path.write_text("# Backlog\n\n## Items\n", encoding="utf-8")
    _, out = _select(path)
    assert out["verdict"] != "BACKLOG_INVALID", out["verdict"]
def test_the_lead_stops_on_it_without_needing_to_know_it() -> None:
    """A new verdict must arrive already handled, not fall through as unrecognised.
    The first draft of this test demanded the literal `BACKLOG_INVALID` in the
    lead, and that was the wrong assertion: the branch is generic — anything that
    is not `ITEM_SELECTED` stops the lead and is reported verbatim — so the new
    verdict was handled before it existed. Requiring the string would have forced
    an edit that changed nothing and taught the next reader to add one per verdict.
    What IS asserted: the branch is generic, and the comment beside it does not
    tell a reader only two verdicts reach there.
    """
    lead = (_REPO / "mechanisms" / "fleet" / "squad_lead.py").read_text(encoding="utf-8")
    assert 'if verdict != "ITEM_SELECTED":' in lead, (
        "the lead stopped handling verdicts generically; a new one now needs a case")
    assert "BACKLOG_INVALID" in lead, (
        "the comment names the verdicts that reach here and omits this one, which "
        "is how a reader concludes the branch does not cover it")
def test_a_content_blocker_alone_does_not_stop_the_registry(tmp_path: Path) -> None:
    """The case that corrected this fix, pinned so it cannot come back.
    `triaged_without_evidence` is a BLOCKER in the checker and has nothing to do
    with identity: the id still names one block. The first draft of the refusal
    keyed on `verdict == "INVALID"` and took every blocker with it, so one item
    triaged without evidence stopped the registry from handing out any work — this
    gate blocking the machine over the very condition the machine exists to fix.
    Three existing tests in this slice caught it.
    """
    sound = _block("B-001")
    weak = _BLOCK.format(iid="B-002", title="Triaged with nothing behind it",
                         evidence="none-yet", status="triaged")
    path = _registry(tmp_path, sound, weak)
    assert _structure_rc(path) == 1, "fixture is not INVALID; it would prove nothing"
    _, out = _select(path)
    assert out["verdict"] == "ITEM_SELECTED", out["verdict"]
    assert out["item_id"] == "B-001", out["item_id"]
def test_a_reused_id_is_refused_and_mere_sequence_is_not(tmp_path: Path) -> None:
    """Both halves, because until #169 this test had the first name and the second fixture.

    It was called `..._a_reused_id_...` and passed `B-005` then `B-002` — two distinct ids,
    nothing reused — so what it actually pinned was that DESCENDING ORDER stops the
    selector. A real consumer's maintenance loop stopped on exactly that, on a 131-item
    registry, the hour its selector caught up with the checker.
    """
    a, b = tmp_path / "reused", tmp_path / "descending"
    a.mkdir(); b.mkdir()
    reused = _registry(a, _block("B-002"), _block("B-002", title="Same id twice"))
    _, out = _select(reused)
    assert out["verdict"] == "BACKLOG_INVALID", out["verdict"]
    assert "duplicate_id" in out["reason"], out["reason"]

    descending = _registry(b, _block("B-005"), _block("B-002", title="Out of sequence"))
    _, out = _select(descending)
    assert out["verdict"] == "ITEM_SELECTED", out["verdict"]
    assert out["item_id"] == "B-002", out["item_id"]
