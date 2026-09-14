"""The brief, and the one status it exists to make writable.

The subject of every test here is a single claim: `approved` means somebody decided.
Anything that would let the status appear without a decision — an unsigned brief, a
signature with nothing ticked, a tick the signature itself applied — is a bug in the
only mechanism that asks the question.
"""
from __future__ import annotations

from pathlib import Path

import build_approval_brief as bb

ITEM = """## {iid} — {title}   [ ]

domain: {domain}
repo: {repo}
suggested_mode: review
source: human
evidence: |
  {evidence}
why_now: {why_first}
  {why_rest}
status: {status}
dod:
  - {dod}
"""


def _registry(tmp_path: Path, *blocks: str) -> Path:
    (tmp_path / "BACKLOG.md").write_text(
        "# Backlog\n\n## Index\n\n(index table here)\n\n## Items\n\n" + "\n".join(blocks),
        encoding="utf-8")
    return tmp_path


def _item(iid="B-001", title="A title", domain="api", repo="api", status="triaged",
          evidence="none-yet", why_first="something changed", why_rest="and it matters",
          dod="a test fails today and passes after") -> str:
    return ITEM.format(iid=iid, title=title, domain=domain, repo=repo, status=status,
                       evidence=evidence, why_first=why_first, why_rest=why_rest, dod=dod)


# ── reading the registry ────────────────────────────────────────────────────

def test_a_wrapped_why_now_is_read_whole(tmp_path):
    """The first version stopped at the first line and truncated every reason.

    `$` under re.M ends before the newline, so the continuation slice began with an
    empty string and the blank-line guard fired immediately. A brief that shows half a
    sentence is worse than one that shows none: the reader believes they read it.
    """
    project = _registry(tmp_path, _item(why_first="the panel redrew D2 on 2026-09-11",
                                        why_rest="and found the asymmetry"))
    items = bb.parse(project / "BACKLOG.md", project, "triaged")
    assert items[0].fields["why_now"] == (
        "the panel redrew D2 on 2026-09-11 and found the asymmetry")


def test_the_index_table_is_not_parsed_as_a_second_registry(tmp_path):
    """Every id appears twice in the file — once in the index, once as an item."""
    project = _registry(tmp_path, _item("B-001"), _item("B-002"))
    text = (project / "BACKLOG.md").read_text(encoding="utf-8")
    (project / "BACKLOG.md").write_text(
        text.replace("(index table here)", "| `B-001` | A title | `triaged` |\n"
                                          "| `B-002` | A title | `triaged` |"),
        encoding="utf-8")
    assert len(bb.parse(project / "BACKLOG.md", project, "triaged")) == 2


def test_only_the_requested_status_is_rendered(tmp_path):
    project = _registry(tmp_path, _item("B-001", status="triaged"),
                        _item("B-002", status="shipped"))
    ids = [i.item_id for i in bb.parse(project / "BACKLOG.md", project, "triaged")]
    assert ids == ["B-001"]


# ── verifying what an item claims ───────────────────────────────────────────

def test_a_pointer_that_resolves_checks_out(tmp_path):
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "policy.yaml").write_text("x\n", encoding="utf-8")
    project = _registry(tmp_path, _item(evidence="infra/policy.yaml:12 — the rule"))
    item = bb.parse(project / "BACKLOG.md", project, "triaged")[0]
    assert item.evidence_verdict == "checks out"


def test_a_pointer_that_does_not_resolve_is_named(tmp_path):
    project = _registry(tmp_path, _item(evidence="infra/gone.yaml:3 — the rule"))
    item = bb.parse(project / "BACKLOG.md", project, "triaged")[0]
    assert item.evidence_verdict == "does not check out"
    assert item.unresolved == ["infra/gone.yaml"]


def test_an_ip_address_is_not_a_missing_file(tmp_path):
    """The false-positive class that cost the most.

    An early version read `10.0.0.0/8` as a path and reported twelve sound items as
    having broken evidence. Over-reporting here is worse than under-reporting: the
    reader stops trusting the column and it might as well not exist.
    """
    project = _registry(tmp_path, _item(
        evidence="except: 10.0.0.0/8, 172.16.0.0/12, 169.254.0.0/16 in the chart"))
    item = bb.parse(project / "BACKLOG.md", project, "triaged")[0]
    assert item.unresolved == []
    assert item.evidence_verdict == "not verifiable"


def test_a_bare_filename_is_a_mention_not_a_pointer(tmp_path):
    """`build_walkthrough.py` in prose names a script; it does not claim a location.

    Measured on a real registry: of 27 bare names, 2 resolved. Treating the other 25
    as broken evidence would have buried the five pointers that were genuinely dead.
    """
    project = _registry(tmp_path, _item(evidence="build_walkthrough.py was never run"))
    item = bb.parse(project / "BACKLOG.md", project, "triaged")[0]
    assert item.pointers_found == 0
    assert item.evidence_verdict == "not verifiable"


def test_not_verifiable_is_not_a_failure(tmp_path):
    """Three outcomes, and the third accuses the item of nothing."""
    project = _registry(tmp_path, _item(evidence="measured in a load test on staging"))
    assert bb.parse(project / "BACKLOG.md", project, "triaged")[0].evidence_verdict \
        == "not verifiable"


def test_a_dotted_directory_can_start_a_path(tmp_path):
    """`.squad/wiki/x.md` matched as `squad/wiki/x.md` under `\\b` and resolved nowhere."""
    (tmp_path / ".squad" / "wiki").mkdir(parents=True)
    (tmp_path / ".squad" / "wiki" / "note.md").write_text("x\n", encoding="utf-8")
    project = _registry(tmp_path, _item(evidence=".squad/wiki/note.md says so"))
    assert bb.parse(project / "BACKLOG.md", project, "triaged")[0].unresolved == []


def test_an_unreadable_neighbour_does_not_kill_the_checker(tmp_path, monkeypatch):
    """`Path.exists()` raises on a directory this process may not stat, and a read-only
    checker that dies reports nothing about the registry it was asked to read."""
    def boom(self):
        raise PermissionError(13, "denied")
    monkeypatch.setattr(Path, "exists", boom)
    project = _registry(tmp_path, _item(evidence="infra/policy.yaml:1"))
    items = bb.parse(project / "BACKLOG.md", project, "triaged")
    assert items[0].evidence_verdict == "does not check out"


# ── what the page offers the reader ─────────────────────────────────────────

def test_every_item_box_starts_empty(tmp_path):
    """Pre-ticking would make the default yes-to-everything."""
    project = _registry(tmp_path, _item("B-001"), _item("B-002"))
    body = bb.render(bb.parse(project / "BACKLOG.md", project, "triaged"),
                     project, "triaged")
    assert body.count("- [ ] **B-") == 2
    assert "- [x]" not in body


def test_the_item_boxes_sit_above_the_signoff(tmp_path):
    """`/sign` ticks every unticked box AFTER the sign-off heading. An item box below
    it would be approved by the act of signing rather than by anyone deciding."""
    project = _registry(tmp_path, _item("B-001"))
    body = bb.render(bb.parse(project / "BACKLOG.md", project, "triaged"),
                     project, "triaged")
    assert body.index("- [ ] **B-001**") < body.index("## Sign-off")


def test_an_item_with_no_dod_is_called_out(tmp_path):
    project = _registry(tmp_path, _item().replace("dod:\n  - a test fails today and passes after\n", ""))
    body = bb.render(bb.parse(project / "BACKLOG.md", project, "triaged"),
                     project, "triaged")
    assert "no closing criterion" in body


# ── the section the item list cannot produce ────────────────────────────────

def test_the_brief_opens_with_coverage_not_with_items(tmp_path):
    """A reader who scrolls straight into the boxes answers the easier half.

    "Do I want each of these" is visible in the list. "Is anything I want missing" is
    not, and it has to be asked before the attention is spent.
    """
    project = _registry(tmp_path, _item("B-001"))
    body = bb.render(bb.parse(project / "BACKLOG.md", project, "triaged"),
                     project, "triaged")
    assert body.index("What this backlog is for") < body.index("## The items")


def test_with_no_objectives_the_brief_says_not_measured(tmp_path):
    project = _registry(tmp_path, _item("B-001"))
    body = bb.render(bb.parse(project / "BACKLOG.md", project, "triaged"),
                     project, "triaged")
    assert "**Not measured.**" in body
    # And it names what would make it answerable, rather than leaving a blank section.
    assert "traces_to" in body


def test_an_unserved_objective_is_stated_in_the_brief(tmp_path):
    objectives = tmp_path / ".squad" / "wiki" / "product" / "objectives.md"
    objectives.parent.mkdir(parents=True)
    objectives.write_text("# Objectives\n\n## OBJ-1 — served\nmetric: x\n\n"
                          "## OBJ-2 — nothing serves this\nmetric: y\n", encoding="utf-8")
    project = _registry(tmp_path, _item("B-001").replace(
        "status: triaged", "traces_to: OBJ-1\nstatus: triaged"))
    body = bb.render(bb.parse(project / "BACKLOG.md", project, "triaged"),
                     project, "triaged")
    assert "1 objective(s) have no item at all" in body
    assert "`OBJ-2`" in body
    # The sentence that matters: ticking everything below still leaves it undone.
    assert "Ticking every box below would still leave it undone" in body


def test_an_item_the_loop_approved_is_not_re_asked(tmp_path):
    """Rendering it would ask the owner to re-make a decision they delegated.

    A sweep finding is born `approved` under a standing authorisation. Putting it back
    in front of a person is what makes autonomy conditional on somebody being awake —
    the failure the standing authorisation exists to remove.
    """
    project = _registry(
        tmp_path,
        _item("B-001"),
        _item("B-002").replace("status: triaged",
                               "status: triaged\napproved_by: system/autonomous-sweep"))
    ids = [i.item_id for i in bb.parse(project / "BACKLOG.md", project, "triaged")]
    assert ids == ["B-001"]


def test_an_item_a_person_approved_is_also_not_re_asked(tmp_path):
    """Same reason, other direction: a decision made is not a decision pending."""
    project = _registry(tmp_path, _item("B-001", status="approved"))
    assert bb.parse(project / "BACKLOG.md", project, "triaged") == []
