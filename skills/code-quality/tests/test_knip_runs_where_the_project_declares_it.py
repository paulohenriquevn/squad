"""D1 reaches knip the way the project's own package manager would.

Measured 2026-09-24 on two repositories of one ecosystem, same kit, same detector:

    knip declared in the root package.json   `npx --yes knip` from root: exit 0, valid JSON
    knip declared in packages/ui only (pnpm) `npx --yes knip` from root: exit 127

and `cd packages/ui && pnpm exec knip` exited 0 with zero findings. The detector read the
127 as `auditor_unavailable_knip`, a soft cap, about a tool that was installed and passing
— capping every plan in that repository at 70 for a reason unrelated to its code.

These tests put a fake `pnpm` / `npx` on PATH that records where it was run and with
what, so they measure the invocation the detector really makes rather than a mock of
`subprocess.run` that would accept any command at all.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from scripts.detectors.typescript import TypescriptDetector

pytestmark = pytest.mark.typescript

_ONE_UNUSED_EXPORT = {"files": [], "exports": [{"file": "src/button.ts", "name": "Unused"}],
                      "dependencies": [], "devDependencies": []}


def _fake_tool(bin_dir: Path, name: str, *, exit_code: int, stdout: dict | None) -> Path:
    """An executable that logs `cwd` and `argv` to `<bin>/<name>.calls`, then answers."""
    log = bin_dir / f"{name}.calls"
    script = bin_dir / name
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"with open({str(log)!r}, 'a') as fh:\n"
        "    fh.write(json.dumps({'cwd': os.getcwd(), 'argv': sys.argv[1:]}) + '\\n')\n"
        f"sys.stdout.write({json.dumps(json.dumps(stdout)) if stdout else repr('')})\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return log


def _calls(log: Path) -> list[dict]:
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A PATH holding only the fakes and the interpreter the fakes need."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python = Path(os.path.realpath(os.sys.executable))
    (bin_dir / "python3").symlink_to(python)
    monkeypatch.setenv("PATH", str(bin_dir))
    return bin_dir


def _package(directory: Path, *, knip: bool, extra: dict | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"name": directory.name, **(extra or {})}
    if knip:
        manifest["devDependencies"] = {"knip": "^6.14.2"}
    (directory / "package.json").write_text(json.dumps(manifest), encoding="utf-8")


def _pnpm_repo(root: Path, *, knip_in_root: bool, knip_in_ui: bool) -> Path:
    _package(root, knip=knip_in_root)
    (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
    (root / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'\n",
                                              encoding="utf-8")
    _package(root / "packages" / "ui", knip=knip_in_ui)
    _package(root / "packages" / "docs", knip=False)
    return root


def test_knip_declared_at_the_root_runs_at_the_root_through_pnpm(
        tmp_path: Path, fake_bin: Path) -> None:
    root = _pnpm_repo(tmp_path / "repo", knip_in_root=True, knip_in_ui=False)
    log = _fake_tool(fake_bin, "pnpm", exit_code=0, stdout=_ONE_UNUSED_EXPORT)

    TypescriptDetector().detect_dead_code(root)

    assert [(c["cwd"], c["argv"][:2]) for c in _calls(log)] == [(str(root), ["exec", "knip"])]


def test_knip_declared_only_in_a_member_is_run_in_that_member(
        tmp_path: Path, fake_bin: Path) -> None:
    root = _pnpm_repo(tmp_path / "repo", knip_in_root=False, knip_in_ui=True)
    log = _fake_tool(fake_bin, "pnpm", exit_code=1, stdout=_ONE_UNUSED_EXPORT)

    TypescriptDetector().detect_dead_code(root)

    assert [c["cwd"] for c in _calls(log)] == [str(root / "packages" / "ui")]


def test_a_member_audit_is_not_reported_as_unavailable(
        tmp_path: Path, fake_bin: Path) -> None:
    root = _pnpm_repo(tmp_path / "repo", knip_in_root=False, knip_in_ui=True)
    _fake_tool(fake_bin, "pnpm", exit_code=0, stdout={"files": [], "exports": []})

    findings = TypescriptDetector().detect_dead_code(root)

    assert [f for f in findings if f.severity != "INFO"] == [], findings


def test_a_member_finding_is_located_from_the_repository_root(
        tmp_path: Path, fake_bin: Path) -> None:
    root = _pnpm_repo(tmp_path / "repo", knip_in_root=False, knip_in_ui=True)
    _fake_tool(fake_bin, "pnpm", exit_code=1, stdout=_ONE_UNUSED_EXPORT)

    findings = TypescriptDetector().detect_dead_code(root)

    assert [f.file_path for f in findings if f.severity == "HARD"] \
        == ["packages/ui/src/button.ts"]


def test_the_report_names_the_directory_a_partial_audit_covered(
        tmp_path: Path, fake_bin: Path) -> None:
    """One package audited is not the tree audited, and must not read as if it were."""
    root = _pnpm_repo(tmp_path / "repo", knip_in_root=False, knip_in_ui=True)
    _fake_tool(fake_bin, "pnpm", exit_code=0, stdout={"files": [], "exports": []})

    findings = TypescriptDetector().detect_dead_code(root)

    scope = [f for f in findings if f.severity == "INFO"]
    assert len(scope) == 1 and "packages/ui" in scope[0].message, findings


def test_knip_declared_nowhere_is_still_auditor_unavailable(
        tmp_path: Path, fake_bin: Path) -> None:
    root = _pnpm_repo(tmp_path / "repo", knip_in_root=False, knip_in_ui=False)
    _fake_tool(fake_bin, "pnpm", exit_code=127, stdout=None)

    findings = TypescriptDetector().detect_dead_code(root)

    assert [f.allowlist_key for f in findings] == ["typescript|.|dead_code|auditor_unavailable_knip"]


def test_a_declared_knip_the_detector_cannot_reach_is_not_measured_not_unavailable(
        tmp_path: Path, fake_bin: Path) -> None:
    """Installed but unreachable is a resolution failure; collapsing it into
    'unavailable' hides the detector's defect behind the project's."""
    root = _pnpm_repo(tmp_path / "repo", knip_in_root=False, knip_in_ui=True)
    # No `pnpm` on PATH at all.

    findings = TypescriptDetector().detect_dead_code(root)

    assert [f.allowlist_key for f in findings] == ["typescript|.|dead_code|auditor_unresolved_knip"]
    assert "not measured" in findings[0].message
    assert "packages/ui" in findings[0].message


def test_a_repository_without_a_lockfile_keeps_npx(tmp_path: Path, fake_bin: Path) -> None:
    _package(tmp_path / "repo", knip=True)
    log = _fake_tool(fake_bin, "npx", exit_code=0, stdout={"files": [], "exports": []})

    TypescriptDetector().detect_dead_code(tmp_path / "repo")

    assert [c["argv"][:2] for c in _calls(log)] == [["--yes", "knip"]]


def test_a_yarn_workspace_member_runs_through_yarn(tmp_path: Path, fake_bin: Path) -> None:
    root = tmp_path / "repo"
    _package(root, knip=False, extra={"workspaces": ["packages/*"]})
    (root / "yarn.lock").write_text("# yarn lockfile v1\n", encoding="utf-8")
    _package(root / "packages" / "ui", knip=True)
    log = _fake_tool(fake_bin, "yarn", exit_code=0, stdout={"files": [], "exports": []})

    TypescriptDetector().detect_dead_code(root)

    assert [(c["cwd"], c["argv"][:1]) for c in _calls(log)] \
        == [(str(root / "packages" / "ui"), ["knip"])]
