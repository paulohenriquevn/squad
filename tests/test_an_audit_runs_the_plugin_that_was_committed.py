"""The kit audited with code that predated the contract it was auditing against.

Claude Code installs a plugin into a CACHE — `~/.claude/plugins/cache/<marketplace>/…` —
and records the `gitCommitSha` it was built from. The kit resolves plugins by
`installPath`, so every audit it commissions runs that snapshot, not the repository.

Measured 2026-09-22 by the session that maintains those plugins, while walking the whole
commission → audit → read chain for the first time: **17 of 18 installed plugins were
behind their repositories.** The contract under test — `compute-verdict --emit-to` — did
not exist in the tree that actually ran. The repository was right. This kit's reader was
right. What executed was neither.

That is the same shape as the retired shell hook wired beside its replacement: each half
honest, the joint wrong, and no test positioned to look at the joint. A premise the kit
depends on and never checked.

It is a PREMISE check, in the sense `check_merge_autonomy` uses: asked once before the
first item rather than per-item, because discovering it per-audit costs the run.

THE THREE ANSWERS STAY APART. `stale` is a measured divergence. `unverifiable` is a source
that is not a local directory, is not a git repository, or an entry carrying no sha — and
it is NOT `aligned`, because the whole defect was a reader treating "I could not ask" as
"nothing is wrong".
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mechanisms" / "gates"))

from check_plugin_freshness import check  # noqa: E402


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def _source(tmp_path: Path, name: str, *, commits: int = 1) -> tuple[Path, str]:
    src = tmp_path / "sources" / name
    src.mkdir(parents=True)
    _git(src, "init", "-q", "-b", "main")
    _git(src, "config", "user.email", "t@example.com")
    _git(src, "config", "user.name", "t")
    for i in range(commits):
        (src / "plugin.md").write_text(f"revision {i}\n", encoding="utf-8")
        _git(src, "add", "-A")
        _git(src, "commit", "-qm", f"r{i}")
    return src, _git(src, "rev-parse", "HEAD")


def _config(tmp_path: Path, plugins: dict) -> Path:
    """A `~/.claude` shaped directory: the two manifests the gate reads."""
    cfg = tmp_path / "config"
    (cfg / "plugins").mkdir(parents=True)
    installed, markets = {}, {}
    for name, (src, sha) in plugins.items():
        cache = tmp_path / "cache" / name
        cache.mkdir(parents=True, exist_ok=True)
        installed[f"{name}@{name}"] = [{
            "scope": "user", "installPath": str(cache), "version": "1.0.0",
            **({"gitCommitSha": sha} if sha is not None else {}),
        }]
        markets[name] = {"source": {"source": "directory", "path": str(src)}}
    (cfg / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": installed}), encoding="utf-8")
    (cfg / "plugins" / "known_marketplaces.json").write_text(
        json.dumps(markets), encoding="utf-8")
    return cfg


def _project(tmp_path: Path, *auditors: str) -> Path:
    project = tmp_path / "project"
    (project / "rules").mkdir(parents=True)
    rows = "\n".join(f"auditor = always | {a} | analysis-scoped" for a in auditors)
    (project / "rules" / "review-auditors.txt").write_text(
        "# rule-id: SQ-PNL-01\nmax_iterations = 40\n" + rows + "\n", encoding="utf-8")
    return project


def test_a_plugin_behind_its_repository_is_reported(tmp_path: Path) -> None:
    src, first = _source(tmp_path, "loop-code-review", commits=1)
    cfg = _config(tmp_path, {"loop-code-review": (src, first)})
    # the repository moves on; the cache does not
    (src / "plugin.md").write_text("the contract the kit audits against\n", encoding="utf-8")
    _git(src, "add", "-A")
    _git(src, "commit", "-qm", "the contract")

    code, report = check(project=_project(tmp_path, "loop-code-review"), config_dir=cfg)

    assert code == 1
    assert [r["plugin"] for r in report["stale"]] == ["loop-code-review"]
    assert report["stale"][0]["installed"] == first
    assert report["aligned"] == []


def test_a_plugin_at_its_repository_head_holds(tmp_path: Path) -> None:
    """THE CONTROL — and the state this machine is in, which is why it is not enough."""
    src, head = _source(tmp_path, "loop-code-review", commits=2)
    cfg = _config(tmp_path, {"loop-code-review": (src, head)})

    code, report = check(project=_project(tmp_path, "loop-code-review"), config_dir=cfg)

    assert code == 0
    assert report["aligned"] == ["loop-code-review"]
    assert report["stale"] == []


def test_an_entry_with_no_sha_is_unverifiable_not_aligned(tmp_path: Path) -> None:
    src, _ = _source(tmp_path, "loop-test-audit", commits=1)
    cfg = _config(tmp_path, {"loop-test-audit": (src, None)})

    code, report = check(project=_project(tmp_path, "loop-test-audit"), config_dir=cfg)

    assert [u["plugin"] for u in report["unverifiable"]] == ["loop-test-audit"]
    assert report["aligned"] == []
    assert code == 0, "unverifiable is not a failure; it is a gap that must be visible"


def test_a_source_that_is_not_local_is_unverifiable(tmp_path: Path) -> None:
    """A plugin installed from GitHub cannot be compared against a tree that is not here.

    Saying so beats both alternatives: calling it aligned is the defect, and failing on it
    would make the gate refuse every machine that installs from a marketplace.
    """
    cfg = _config(tmp_path, {})
    cfgp = cfg / "plugins"
    installed = json.loads((cfgp / "installed_plugins.json").read_text())
    installed["plugins"]["loop-doc-audit@remote"] = [
        {"scope": "user", "installPath": str(tmp_path / "cache" / "x"),
         "version": "1.0.0", "gitCommitSha": "a" * 40}]
    (cfgp / "installed_plugins.json").write_text(json.dumps(installed), encoding="utf-8")
    markets = json.loads((cfgp / "known_marketplaces.json").read_text())
    markets["remote"] = {"source": {"source": "github", "repo": "someone/loop-doc-audit"}}
    (cfgp / "known_marketplaces.json").write_text(json.dumps(markets), encoding="utf-8")

    _, report = check(project=_project(tmp_path, "loop-doc-audit"), config_dir=cfg)

    assert [u["plugin"] for u in report["unverifiable"]] == ["loop-doc-audit"]
    assert "not a local" in report["unverifiable"][0]["why"]


def test_a_plugin_nobody_commissions_is_not_measured(tmp_path: Path) -> None:
    """Scope is the registry. Drift in a plugin no REVIEW ever runs is not this gate's."""
    used, head_used = _source(tmp_path, "loop-code-review", commits=1)
    idle, head_idle = _source(tmp_path, "loop-project-purge", commits=1)
    cfg = _config(tmp_path, {"loop-code-review": (used, head_used),
                             "loop-project-purge": (idle, head_idle)})
    (idle / "plugin.md").write_text("moved on\n", encoding="utf-8")
    _git(idle, "add", "-A")
    _git(idle, "commit", "-qm", "moved")

    code, report = check(project=_project(tmp_path, "loop-code-review"), config_dir=cfg)

    assert code == 0
    assert report["stale"] == []
    assert "loop-project-purge" not in report["aligned"]


def test_a_commissioned_plugin_that_is_not_installed_is_unverifiable(tmp_path: Path) -> None:
    """An absent plugin is `select_auditors`' exit 3, not a freshness verdict.

    Reporting it as stale would send the reader to update something they do not have.
    """
    cfg = _config(tmp_path, {})

    _, report = check(project=_project(tmp_path, "loop-code-review"), config_dir=cfg)

    assert [u["plugin"] for u in report["unverifiable"]] == ["loop-code-review"]
    assert "not installed" in report["unverifiable"][0]["why"]


def test_no_registry_is_unmeasured_rather_than_clean(tmp_path: Path) -> None:
    project = tmp_path / "bare"
    project.mkdir()

    code, report = check(project=project, config_dir=_config(tmp_path, {}))

    assert code == 2, "a project with no auditor registry was not measured"
    assert report["state"] == "unmeasured"
