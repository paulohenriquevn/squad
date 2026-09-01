"""Intake gates G1 and G2 were mechanizable and were not mechanized.

`/backlog-item` declares five hard gates and shipped not a single script. G3
(single domain), G4 (verifiable DoD) and G5 (no prior art) are judgement and stay
conversational, covered by evals. G1 (the repo resolves) and G2 (the dedup search
ran) are not: `scripts/route_domain.py` already existed, with 23 tests, and the
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
    (root / "scripts").mkdir(parents=True)
    (root / "rules").mkdir()
    (root / "agents").mkdir()
    (root / "scripts" / "route_domain.py").write_bytes(
        (REPO_ROOT / "scripts" / "route_domain.py").read_bytes()
    )
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
