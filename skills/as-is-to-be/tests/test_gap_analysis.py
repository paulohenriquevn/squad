"""Current state against future state, and the three claims it must never make.

The page is persuasive by construction — a list of promises reads like a plan. Every
test here defends a boundary on what it is allowed to assert, because the failure mode
of a gap analysis is not being wrong about an item; it is being read as complete.
"""
from __future__ import annotations

from pathlib import Path

import build_gap_analysis as gap

ITEM = """## {iid} — {title}   [ ]

domain: {domain}
repo: api
suggested_mode: review
source: human
evidence: |
  {evidence}
why_now: {why}
status: {status}
{blocked}dod:
{dod}
"""


def _item(iid="B-001", title="A title", domain="api", status="triaged",
          evidence="infra/policy.yaml:12 — the rule is absent",
          why="the panel found it", dod=("a test fails today",), blocked=""):
    return ITEM.format(
        iid=iid, title=title, domain=domain, status=status, evidence=evidence, why=why,
        blocked=f"blocked_by: {blocked}\n" if blocked else "",
        dod="".join(f"  - {b}\n" for b in dod))


def _project(tmp_path: Path, *blocks: str) -> Path:
    (tmp_path / "BACKLOG.md").write_text(
        "# Backlog\n\n## Index\n\n(table)\n\n## Items\n\n" + "\n".join(blocks),
        encoding="utf-8")
    return tmp_path


# ── the projection itself ───────────────────────────────────────────────────

def test_evidence_becomes_the_current_state_and_dod_the_future_one(tmp_path):
    """No new field is asked for: both halves were already in the item."""
    project = _project(tmp_path, _item(
        evidence="grep -c cnpg cell.yaml -> 0",
        dod=("one CNPG instance per cell", "the operator is Ready first")))
    row = gap.rows(project, "triaged")[0]
    assert "grep -c cnpg" in row.as_is
    assert row.to_be == ["one CNPG instance per cell", "the operator is Ready first"]


def test_items_are_grouped_by_domain(tmp_path):
    project = _project(tmp_path, _item("B-001", domain="api"),
                       _item("B-002", domain="cells"), _item("B-003", domain="api"))
    body = gap.render_markdown(gap.rows(project, "triaged"), project, "triaged")
    assert "## `api` — 2 item(s)" in body
    assert "## `cells` — 1 item(s)" in body


def test_only_the_requested_status_is_projected(tmp_path):
    project = _project(tmp_path, _item("B-001", status="triaged"),
                       _item("B-002", status="shipped"))
    assert [r.item_id for r in gap.rows(project, "triaged")] == ["B-001"]


def test_the_promise_count_is_bullets_not_items(tmp_path):
    """Twenty items with three bullets each is sixty promises, and that is the number
    that says how much is being committed to."""
    project = _project(tmp_path, _item("B-001", dod=("a", "b", "c")),
                       _item("B-002", dod=("d", "e")))
    body = gap.render_markdown(gap.rows(project, "triaged"), project, "triaged")
    assert "5 promise(s)" in body


# ── the three refusals ──────────────────────────────────────────────────────

def test_the_page_states_that_the_current_state_is_only_what_items_measured(tmp_path):
    """A part of the system nobody filed an item against is absent, and is not fine."""
    body = gap.render_markdown(gap.rows(_project(tmp_path, _item()), "triaged"),
                               tmp_path, "triaged")
    assert "union of what these items happened to measure" in body
    assert "not thereby fine" in body


def test_the_page_refuses_to_claim_the_future_state_is_coherent(tmp_path):
    """Two items may promise contradictory things and nothing here can tell."""
    body = gap.render_markdown(gap.rows(_project(tmp_path, _item()), "triaged"),
                               tmp_path, "triaged")
    assert "not checked for coherence" in body


def test_the_page_refuses_to_claim_the_work_will_succeed(tmp_path):
    """A triaged item has evidence for the problem, never proof the solution works."""
    body = gap.render_markdown(gap.rows(_project(tmp_path, _item()), "triaged"),
                               tmp_path, "triaged")
    assert "evidence for the problem is not proof the solution works" in body


# ── what it inherits from the verifier ──────────────────────────────────────

def test_a_current_state_whose_pointer_is_dead_is_marked_not_hidden(tmp_path):
    """The whole page rests on the AS-IS being a measurement. One that cannot be
    followed has to look different from one that can."""
    project = _project(tmp_path, _item(evidence="infra/gone.yaml:3 — absent"))
    body = gap.render_markdown(gap.rows(project, "triaged"), project, "triaged")
    assert "**pointer does not resolve**" in body


def test_a_current_state_that_resolves_is_marked_measured(tmp_path):
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "policy.yaml").write_text("x\n", encoding="utf-8")
    project = _project(tmp_path, _item(evidence="infra/policy.yaml:12 — absent"))
    body = gap.render_markdown(gap.rows(project, "triaged"), project, "triaged")
    assert "(measured)" in body


def test_an_ip_address_does_not_become_a_broken_pointer(tmp_path):
    """Inherited from the same conservative extraction: over-reporting a dead pointer
    costs more than missing one, because the reader stops trusting the mark."""
    project = _project(tmp_path, _item(evidence="except 10.0.0.0/8 and 172.16.0.0/12"))
    assert gap.rows(project, "triaged")[0].as_is_verified == "not verifiable"


# ── the parts that would be silently missing ────────────────────────────────

def test_an_item_with_no_dod_says_so_rather_than_rendering_an_empty_after(tmp_path):
    """An empty 'After' reads as an item that changes nothing."""
    project = _project(tmp_path, _item(dod=()))
    body = gap.render_markdown(gap.rows(project, "triaged"), project, "triaged")
    assert "no closing criterion" in body


def test_a_blocked_item_says_it_cannot_start(tmp_path):
    """A future state built from work that cannot begin is a different promise."""
    project = _project(tmp_path, _item(blocked="B-002"))
    body = gap.render_markdown(gap.rows(project, "triaged"), project, "triaged")
    assert "Cannot start:" in body and "B-002" in body


def test_an_objective_no_item_serves_is_named_on_this_page_too(tmp_path):
    """The future state below does not reach it, however many items are done."""
    objectives = tmp_path / ".squad" / "wiki" / "product" / "objectives.md"
    objectives.parent.mkdir(parents=True)
    objectives.write_text("# Objectives\n\n## OBJ-1 — served\nmetric: x\n\n"
                          "## OBJ-2 — unserved\nmetric: y\n", encoding="utf-8")
    project = _project(tmp_path, _item().replace("status: triaged",
                                                 "traces_to: OBJ-1\nstatus: triaged"))
    body = gap.render_markdown(gap.rows(project, "triaged"), project, "triaged")
    assert "`OBJ-2`" in body
    assert "does not reach them" in body


def test_no_registry_is_not_measured(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["build_gap_analysis.py", str(tmp_path)])
    assert gap.main() == 2
