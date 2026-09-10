"""Which independent auditors a change must face, and who decides.

The rule under every test here: the selection is DERIVED, never chosen. Letting the
reviewing agent pick its own auditor is the failure the review panel already refuses
when it will not seat an author — point a concurrency change at a docs auditor and the
report comes back clean, honestly, having looked at nothing that mattered.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "cycle"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mechanisms" / "conventions"))

from select_auditors import (
    INVALID,
    NOT_INSTALLED,
    OK,
    parse_registry,
    required_for,
    select,
)

REGISTRY = """
auditor = always      | loop-code-review       | analysis-scoped 
auditor = security    | loop-security-audit    | analysis-scoped 
auditor = database    | loop-performance-audit | analysis-scoped 
auditor = concurrency | loop-performance-audit | analysis-scoped 
auditor = api-design  | loop-surface-closure   | report-filtered 
"""

ALL_PLUGINS = ("loop-code-review", "loop-security-audit", "loop-performance-audit",
               "loop-surface-closure")


def _project(tmp_path: Path, registry: str | None = REGISTRY) -> Path:
    root = tmp_path / "proj"
    (root / "rules").mkdir(parents=True, exist_ok=True)
    if registry is not None:
        (root / "rules" / "review-auditors.txt").write_text(registry, encoding="utf-8")
    return root


def _config(tmp_path: Path, *installed: str) -> Path:
    cfg = tmp_path / "claude"
    (cfg / "plugins").mkdir(parents=True, exist_ok=True)
    entries = {}
    for name in installed:
        tree = tmp_path / "installed" / name
        tree.mkdir(parents=True, exist_ok=True)
        entries[f"{name}@m"] = [{"installPath": str(tree), "version": "1.0.0"}]
    (cfg / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": entries}), encoding="utf-8")
    return cfg


def _select(tmp_path, domains, **kw):
    return select("B-014", domains, project=_project(tmp_path, kw.pop("registry", REGISTRY)),
                  config_dir=_config(tmp_path, *kw.pop("installed", ALL_PLUGINS)), **kw)


def test_the_always_auditor_runs_whatever_the_change_is_about(tmp_path: Path) -> None:
    code, result = _select(tmp_path, [])

    assert code == OK
    assert [r["plugin"] for r in result["required"]] == ["loop-code-review"]


def test_a_domain_pulls_in_its_auditor(tmp_path: Path) -> None:
    _, result = _select(tmp_path, ["security"])

    assert {r["plugin"] for r in result["required"]} == {
        "loop-code-review", "loop-security-audit"}


def test_two_domains_reaching_one_plugin_is_one_audit(tmp_path: Path) -> None:
    """`database` and `concurrency` both reach the performance auditor. Running it
    twice buys a second copy of the same report."""
    _, result = _select(tmp_path, ["database", "concurrency"])

    plugins = [r["plugin"] for r in result["required"]]
    assert plugins.count("loop-performance-audit") == 1


def test_an_unmapped_domain_still_gets_the_always_auditor(tmp_path: Path) -> None:
    """An unknown domain must not silently mean 'no audit'."""
    _, result = _select(tmp_path, ["something-nobody-mapped"])

    assert [r["plugin"] for r in result["required"]] == ["loop-code-review"]


def test_a_scoped_run_names_its_base(tmp_path: Path) -> None:
    _, result = _select(tmp_path, ["security"], diff_base="develop")

    assert result["scope"]["kind"] == "change"
    assert result["scope"]["diff_base"] == "develop"
    assert all("--diff-base develop" in r["command"] for r in result["required"])


def test_an_unscoped_run_says_so_in_writing(tmp_path: Path) -> None:
    """Guessing a base is how `sq test --touched` once selected 792 files. An
    unscoped run is a defensible answer; a silently wrong scope is not."""
    _, result = _select(tmp_path, ["security"])

    assert result["scope"]["kind"] == "whole_tree"
    assert "WHOLE TREE" in result["scope"]["detail"]
    assert all("--diff-base" not in r["command"] for r in result["required"])


def test_the_declared_diff_mode_travels(tmp_path: Path) -> None:
    """`report-filtered` exists because reachability and duplication are properties of
    the whole graph — analysing the diff alone would make every new function orphaned."""
    _, result = _select(tmp_path, ["api-design"], diff_base="main")

    modes = {r["plugin"]: r["diff_mode"] for r in result["required"]}
    assert modes["loop-surface-closure"] == "report-filtered"
    assert modes["loop-code-review"] == "analysis-scoped"


def test_a_required_plugin_that_is_not_installed_is_a_coverage_gap(tmp_path: Path) -> None:
    """Not a defect in the code, and not a clean review either."""
    code, result = _select(tmp_path, ["security"], installed=("loop-code-review",))

    assert code == NOT_INSTALLED
    assert result["missing_plugins"] == ["loop-security-audit"]
    assert "access" in result["detail"]


def test_an_unknown_diff_mode_is_refused(tmp_path: Path) -> None:
    """Recording the wrong mode would let a diff-only analysis read as whole-tree."""
    code, result = _select(tmp_path, [],
                           registry="auditor = always | p | sometimes\n")

    assert code == INVALID
    assert "diff mode" in result["detail"]


def test_a_half_written_row_is_refused_not_skipped(tmp_path: Path) -> None:
    """A malformed row must never parse to 'no auditor' and read as a domain nobody
    needed to audit."""
    code, _ = _select(tmp_path, [], registry="auditor = always\n")

    assert code == INVALID


def test_a_project_declaring_no_auditor_says_so(tmp_path: Path) -> None:
    """The opt-out is visible. An empty result that means 'nothing required' and one
    that means 'the file is missing' would otherwise look identical."""
    code, result = _select(tmp_path, ["security"], registry="# nothing here\n")

    assert code == OK
    assert result["status"] == "none_declared"


def test_comments_are_not_auditors(tmp_path: Path) -> None:
    body = "# auditor = always | ghost | analysis-scoped | out\n" + REGISTRY
    assert len(parse_registry(body)) == len(parse_registry(REGISTRY))


def test_required_for_is_stable_in_order(tmp_path: Path) -> None:
    """A set would reorder between runs and make the assignment file churn."""
    auditors = parse_registry(REGISTRY)
    a = [x.plugin for x in required_for(auditors, ["security", "database"])]
    b = [x.plugin for x in required_for(auditors, ["database", "security"])]

    assert a == b == sorted(a)


def test_a_pull_request_names_the_change_too(tmp_path: Path) -> None:
    """The plugins accept three forms; a REVIEW of a PR is a real case."""
    _, result = _select(tmp_path, ["security"], pr="142")

    assert result["scope"]["named_by"] == "--pr"
    assert all("--pr 142" in r["command"] for r in result["required"])


def test_a_commit_range_names_the_change_too(tmp_path: Path) -> None:
    _, result = _select(tmp_path, [], commits="abc..def")

    assert result["scope"]["kind"] == "change"
    assert "--commits abc..def" in result["required"][0]["command"]


def test_naming_the_change_twice_is_refused(tmp_path: Path) -> None:
    """Which would win is undefined in the plugins, so it is undefined here — and an
    undefined scope silently audits the wrong thing."""
    code, result = _select(tmp_path, [], diff_base="main", pr="142")

    assert code == INVALID
    assert "named twice" in result["detail"]
