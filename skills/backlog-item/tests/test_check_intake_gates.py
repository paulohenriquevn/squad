"""Intake gates G1 and G2 were mechanizable and were not mechanized.

`/backlog-item` declares five hard gates and shipped not a single script. G3
(single domain), G4 (verifiable DoD) and G5 (no prior art) are judgement and stay
conversational, covered by evals. G1 (the repo resolves) and G2 (the dedup search
ran) are not: `mechanisms/cycle/route_domain.py` already existed, with 23 tests, and the
skill did not call it — it instructed an inline `python3 -c` and a `grep` nobody
verified. A gate whose execution depends on the agent remembering is not a gate.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_intake_gates.py"
REPO_ROOT = Path(__file__).resolve().parents[3]

# G1 routes through the project's table, which is why the project is BUILT here
# instead of pointing at this repository. While it pointed, the test measured the
# machine's configuration: it stayed green for months because
# `rules/cycle-backlog.md` carried the table of the ecosystem the kit was written
# in, and broke the day that table left — with nothing in `check_intake_gates.py`
# having changed.

BACKLOG = """# Backlog

## Index

## B-007 — Suspected N+1 in alpha-lens's ingest path   [ ]

domain: ingest
repo: alpha-lens
status: raw
why_now: ingest got slow after the last deploy

## B-008 — Explorer de traces com p95 alto   [x]

domain: ingest
repo: alpha-lens
status: shipped

## B-009 — Session cache nobody measured   [ ]

domain: ingest
repo: alpha-lens
status: killed
"""


def _project(tmp_path: Path) -> Path:
    """A project with a routing table of its own and the specialists it names."""
    root = tmp_path / "projeto"
    (root / "mechanisms" / "cycle").mkdir(parents=True)
    (root / "rules").mkdir()
    (root / "agents").mkdir()
    (root / "mechanisms" / "cycle" / "route_domain.py").write_bytes(
        (REPO_ROOT / "mechanisms" / "cycle" / "route_domain.py").read_bytes()
    )
    # `install.sh` copies `squad/` beside `mechanisms/`, and `route_domain.py` reads
    # the write root's name from it. A fixture with one and not the other models an
    # install that does not exist.
    (root / "squad").mkdir(exist_ok=True)
    (root / "squad" / "paths.py").write_bytes(
        (REPO_ROOT / "squad" / "paths.py").read_bytes())
    (root / "rules" / "cycle-backlog.md").write_text(
        "# Cycle: BACKLOG\n\n## Domain routing\n\n"
        "| Domain | Repos | Specialist |\n|---|---|---|\n"
        "| `ingest` | `alpha-lens` | `agents/ingest.md` |\n"
        "| `search` | `alpha-rag` | `agents/search.md` |\n\n"
        "## Verdicts\n",
        encoding="utf-8",
    )
    for name in ("ingest", "search"):
        (root / "agents" / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")
    return root


def _run(backlog: Path, repo: str, terms: list[str]) -> tuple[int, dict]:
    args = [
        sys.executable, str(SCRIPT),
        "--backlog", str(backlog),
        "--repo", repo,
        "--project-root", str(_project(backlog.parent)),
    ]
    for term in terms:
        args.extend(["--term", term])
    result = subprocess.run(args, capture_output=True, text=True)  # noqa: PLW1510
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {"raw": result.stdout, "stderr": result.stderr}
    return result.returncode, data


def _backlog(tmp_path: Path) -> Path:
    path = tmp_path / "BACKLOG.md"
    path.write_text(BACKLOG, encoding="utf-8")
    return path


def test_unknown_repo_is_refused_by_g1(tmp_path: Path) -> None:
    rc, data = _run(_backlog(tmp_path), "repo-that-does-not-exist", ["cache"])
    assert rc == 1
    assert data["verdict"] == "ITEM_REJECTED"
    assert data["g1"]["routed"] is False


def test_known_repo_routes_and_names_the_specialist(tmp_path: Path) -> None:
    _rc, data = _run(_backlog(tmp_path), "alpha-rag", ["nada-casa-aqui"])
    assert data["g1"]["routed"] is True
    assert data["g1"]["domain"]
    assert data["g1"]["agent"]


def test_no_dedup_hit_passes_both_gates(tmp_path: Path) -> None:
    """A repo with no item in the registry: G1 routes, G2 searched and found nothing."""
    rc, data = _run(_backlog(tmp_path), "alpha-rag", ["nada-casa-aqui"])
    assert rc == 0
    assert data["verdict"] == "GATES_PASS"
    assert data["g2"]["searched"] is True
    assert data["g2"]["candidates"] == []


def test_open_item_hit_recommends_merge(tmp_path: Path) -> None:
    rc, data = _run(_backlog(tmp_path), "alpha-lens", ["ingest"])
    assert rc == 3
    assert data["verdict"] == "DEDUP_CANDIDATES"
    candidate = next(c for c in data["g2"]["candidates"] if c["id"] == "B-007")
    assert candidate["status"] == "raw"
    assert candidate["recommended_action"] == "ITEM_MERGED"


def test_shipped_item_hit_recommends_regression_link(tmp_path: Path) -> None:
    _rc, data = _run(_backlog(tmp_path), "alpha-lens", ["traces"])
    candidate = next(c for c in data["g2"]["candidates"] if c["id"] == "B-008")
    assert candidate["recommended_action"] == "regression_of"


def test_killed_item_hit_recommends_supersedes(tmp_path: Path) -> None:
    _rc, data = _run(_backlog(tmp_path), "alpha-lens", ["cache"])
    candidate = next(c for c in data["g2"]["candidates"] if c["id"] == "B-009")
    assert candidate["recommended_action"] == "supersedes"


def test_the_repo_name_itself_is_always_a_search_term(tmp_path: Path) -> None:
    """The skill says to search the nouns PLUS the repo; leaving that to the caller
    is how the repo dropped out of the search with nobody noticing."""
    _rc, data = _run(_backlog(tmp_path), "alpha-lens", [])
    assert "alpha-lens" in data["g2"]["terms"]
    assert data["g2"]["candidates"], data


def test_missing_backlog_fails_loudly(tmp_path: Path) -> None:
    rc, _data = _run(tmp_path / "does-not-exist.md", "alpha-lens", ["x"])
    assert rc == 2


# ── could-not-judge is not refused ────────────────────────────────────────────
#
# Every error path used to collapse into ITEM_REJECTED / exit 1 — the verdict the
# contract defines as "the item was refused". None of these three paths had a test,
# which is why the collapse survived: the three error branches of `_route` were never
# executed by the suite.
#
# The distinction is not cosmetic. A refused item gets reworded; an unreadable table
# gets derived. Telling a filer the first when the second is true sends them to fix
# something that was never broken.


def _run_raw(project: Path, repo: str, backlog: Path) -> subprocess.CompletedProcess[str]:
    """Distinct from `_run` above, which builds its own project and returns a tuple.

    These tests MUTATE the project — deleting the routing tool, breaking the table,
    removing a specialist — so they need to hold the project they broke.
    """
    return subprocess.run(  # noqa: PLW1510
        [sys.executable, str(SCRIPT), "--backlog", str(backlog),
         "--repo", repo, "--project-root", str(project)],
        capture_output=True, text=True,
    )


def test_an_unreadable_routing_table_is_inconclusive_not_a_refusal(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "rules" / "cycle-backlog.md").write_text(
        "# Cycle: BACKLOG\n\n## Domain routing\n\nno rows here at all\n\n## Verdicts\n",
        encoding="utf-8",
    )
    (project / "rules" / "domain-routing.txt").write_text("garbage\n", encoding="utf-8")
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(BACKLOG, encoding="utf-8")

    result = _run_raw(project, "alpha-lens", backlog)

    assert result.returncode == 2, result.stdout
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "GATE_INCONCLUSIVE"
    assert payload["g1"]["reason"] == "routing_table_unreadable"
    assert "detect_domains.py" in payload["action"], "must say how to fix it"
    assert "not judged" in payload["action"].lower(), "must not read as a verdict on the item"


def test_a_missing_routing_tool_is_inconclusive(tmp_path: Path) -> None:
    """The tool is absent, so routing was never assessed."""
    project = _project(tmp_path)
    (project / "mechanisms" / "cycle" / "route_domain.py").unlink()
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(BACKLOG, encoding="utf-8")

    result = _run_raw(project, "alpha-lens", backlog)

    assert result.returncode == 2, result.stdout
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "GATE_INCONCLUSIVE"
    assert payload["g1"]["reason"] == "route_domain_missing"


def test_a_broken_route_refuses_and_names_the_missing_specialist(tmp_path: Path) -> None:
    """The table read fine and the answer is no — a judgement, so a refusal.

    Distinct from an unroutable repo: the repo IS in the table and the specialist
    file is not on disk, so the fix is writing that file, never rewording the item.
    """
    project = _project(tmp_path)
    (project / "agents" / "ingest.md").unlink()
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(BACKLOG, encoding="utf-8")

    result = _run_raw(project, "alpha-lens", backlog)

    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "ITEM_REJECTED"
    assert payload["g1"]["reason"] == "broken_route"
    assert "do NOT stand in" in payload["action"]


def test_an_unroutable_repo_is_refused_and_says_so_differently(tmp_path: Path) -> None:
    project = _project(tmp_path)
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(BACKLOG, encoding="utf-8")

    result = _run_raw(project, "not-a-repo-here", backlog)

    assert result.returncode == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "ITEM_REJECTED"
    assert payload["g1"]["reason"] == "unroutable_repo"
    assert "domain-routing.txt" in payload["action"]


def test_the_four_outcomes_have_four_distinct_exit_codes(tmp_path: Path) -> None:
    """A caller branching on the exit code must be able to tell them apart."""
    project = _project(tmp_path)
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(BACKLOG, encoding="utf-8")

    assert _run_raw(project, "alpha-rag", backlog).returncode == 0          # GATES_PASS
    assert _run_raw(project, "nope", backlog).returncode == 1               # ITEM_REJECTED
    assert _run_raw(project, "alpha-lens", backlog).returncode == 3         # DEDUP_CANDIDATES

    (project / "mechanisms" / "cycle" / "route_domain.py").unlink()
    result = _run_raw(project, "alpha-rag", backlog)
    assert result.returncode == 2                                          # GATE_INCONCLUSIVE
    # Not just the code: the REASON has to be there. Asserting the exit alone let a
    # reverted fix pass this test, because `outcome` defaulted to inconclusive when
    # absent — a silent default that hid exactly the class of bug being fixed.
    assert json.loads(result.stdout)["g1"]["reason"] == "route_domain_missing"


# ── the judgement gates are covered by evals, and that claim is now checked ────


def test_every_judgement_gate_has_an_eval_of_its_own() -> None:
    """`check_intake_gates.py` justifies leaving G3, G4 and G5 conversational by
    saying the eval battery covers exactly them.

    G4 had no case of its own: it appeared only as a secondary assertion inside the
    happy-path eval, so the gate was never exercised FIRING while G3 and G5 both
    were. The docstring asserted a coverage that did not exist — the same
    contract-without-mechanism shape this file was already fixed for once.

    This test is the mechanism. It does not judge whether the evals are GOOD; only
    a run answers that. It refuses the case where a gate is claimed covered and no
    case names it.
    """
    battery = json.loads(
        (Path(__file__).parent.parent / "evals" / "evals.json").read_text(encoding="utf-8")
    )
    names = " ".join(e["name"] for e in battery["evals"])
    for gate in ("G3", "G4", "G5"):
        assert gate in names, (
            f"{gate} is called conversational-and-eval-covered by the script's "
            f"docstring, and no eval case names it: {names}"
        )


# ---------------------------------------------------------------------------
# G5 has an executable route for the items the system itself creates
# ---------------------------------------------------------------------------

def _stream(root: Path, *events: dict) -> Path:
    d = root / ".squad" / "records"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "cycle-events.jsonl"
    f.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return f


def _g5():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from check_intake_gates import g5_route
    return g5_route


def test_a_halt_born_item_answers_g5_by_lookup(tmp_path: Path) -> None:
    """The recirculation an external reviewer found.

    Halts return work to the registry, so an autonomous run reaches the entrance again —
    and `cycle-backlog.md` says a person decides G5 there. "Zero interventions after
    BACKLOG" does not survive that.

    An item a halt produced has a `why_now` that is a citation into this project's own
    stream, not a claim about another project. G5's question is then a lookup.
    """
    _stream(tmp_path, {"cycle": "implement", "verdict": "NEEDS_FIXES", "slug": "B-014"})

    result = _g5()("implement ended NEEDS_FIXES for B-014", tmp_path)

    assert result["outcome"] == "mechanized"
    assert result["evidence"]["slug"] == "B-014"


def test_an_unconfirmable_citation_stays_with_a_person(tmp_path: Path) -> None:
    """G5's harder half, measured on 2026-08-28: a model refused the prior-art
    justification and then invented a local one. A citation nobody can confirm is
    exactly that, so the route must not accept the SHAPE of a citation."""
    _stream(tmp_path, {"cycle": "implement", "verdict": "NEEDS_FIXES", "slug": "B-014"})

    result = _g5()("implement ended NEEDS_FIXES for B-999", tmp_path)

    assert result["outcome"] == "human"
    assert "does not carry it" in result["reason"]


def test_an_appeal_to_another_project_stays_with_a_person(tmp_path: Path) -> None:
    _stream(tmp_path, {"cycle": "implement", "verdict": "NEEDS_FIXES", "slug": "B-014"})
    g5 = _g5()

    assert g5("project X does it this way", tmp_path)["outcome"] == "human"
    assert g5("", tmp_path)["outcome"] == "human"


def test_no_stream_on_disk_is_not_a_confirmation(tmp_path: Path) -> None:
    """Absence of evidence read as evidence is the failure this kit is built around."""
    assert _g5()("implement ended NEEDS_FIXES for B-014", tmp_path)["outcome"] == "human"
