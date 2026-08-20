"""B-059 — the version lives in two files and a human keeps them in step.

Measured 2026-08-19 on the tracked tree: `git ls-files -z | xargs -0 grep -ln "0\\.65\\.0"` returns
exactly `package.json` and `src/index.ts` (CHANGELOG and the lockfile excluded). No residue of the
previous version anywhere — so the two ARE kept in step, by hand, every release.

The failure mode is not "a wrong version ships": the export-surface contract test catches the drift,
and it did, at 0.63.0 — `expected '0.62.0' to be '0.63.0'`, aborting `npm publish` AFTER the tag was
cut and pushed. `v0.63.0` still points at a commit whose exported constant is wrong. The failure
mode is that a human bumps two files and finds out at publish time when they miss one.

Every fixture builds its own tree in `tmp_path`. A test that read this repository would pass or fail
on today's version number.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "bump_version.py"

OLD = "1.2.3"
NEW = "1.3.0"


def _tree(tmp_path: Path, index_version: str = OLD, stray: str | None = None) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "package.json").write_text(
        json.dumps({"name": "@x/y", "version": OLD}, indent=2) + "\n", encoding="utf-8"
    )
    (root / "src" / "index.ts").write_text(
        f'// entry\nexport const VERSION = "{index_version}";\n\nexport * from "./a.js";\n',
        encoding="utf-8",
    )
    if stray is not None:
        (root / stray).parent.mkdir(parents=True, exist_ok=True)
        (root / stray).write_text(f'const documented = "{OLD}";\n', encoding="utf-8")

    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin", "HOME": str(root)}
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True, env=env)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed"],
                   cwd=root, check=True, capture_output=True, env=env)
    return root


def _run(root: Path, frm: str = OLD, to: str = NEW) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--from", frm, "--to", to],
        capture_output=True, text=True, check=False,
    )


def test_both_declared_sites_are_rewritten(tmp_path: Path) -> None:
    root = _tree(tmp_path)

    result = _run(root)

    assert result.returncode == 0, result.stderr
    manifest = (root / "package.json").read_text(encoding="utf-8")
    entry = (root / "src" / "index.ts").read_text(encoding="utf-8")
    assert f'"version": "{NEW}"' in manifest
    assert f'VERSION = "{NEW}"' in entry
    assert OLD not in manifest
    assert OLD not in entry


def test_an_undeclared_occurrence_is_reported_and_not_rewritten(tmp_path: Path) -> None:
    # A version string in a fixture, a documented install line or a lockfile is NOT a site.
    # Rewriting it is a corruption no gate would catch, so the script names it and refuses.
    root = _tree(tmp_path, stray="docs/example.ts")
    before = (root / "docs" / "example.ts").read_text(encoding="utf-8")

    result = _run(root)

    assert result.returncode != 0
    assert "docs/example.ts" in (result.stdout + result.stderr)
    assert (root / "docs" / "example.ts").read_text(encoding="utf-8") == before


def test_an_unexpected_current_version_is_refused_without_writing(tmp_path: Path) -> None:
    # If a site does not carry the version the release assumes, the tree is not in the state the
    # release assumes. Writing anyway hides why.
    root = _tree(tmp_path, index_version="9.9.9")
    manifest_before = (root / "package.json").read_text(encoding="utf-8")
    entry_before = (root / "src" / "index.ts").read_text(encoding="utf-8")

    result = _run(root)

    assert result.returncode != 0
    # Naming the site is what makes this a refusal rather than a crash — without it the test would
    # pass against a script that does not exist, which is a vacuous pass.
    assert "src/index.ts" in (result.stdout + result.stderr)
    assert (root / "package.json").read_text(encoding="utf-8") == manifest_before
    assert (root / "src" / "index.ts").read_text(encoding="utf-8") == entry_before


def test_a_no_op_bump_succeeds_and_changes_nothing(tmp_path: Path) -> None:
    # Running it for the version already in place is how a release verifies the tree before cutting.
    root = _tree(tmp_path)
    before = (root / "package.json").read_text(encoding="utf-8")

    result = _run(root, frm=OLD, to=OLD)

    assert result.returncode == 0, result.stderr
    assert (root / "package.json").read_text(encoding="utf-8") == before


def test_it_reports_the_sites_it_wrote(tmp_path: Path) -> None:
    # A script that exits 0 without saying what it did is indistinguishable from one that did
    # nothing — which is the failure this whole item is about, one layer up.
    root = _tree(tmp_path)

    result = _run(root)

    assert "package.json" in result.stdout
    assert "src/index.ts" in result.stdout


def test_the_changelog_carrying_every_version_is_not_a_stray(tmp_path: Path) -> None:
    # The CHANGELOG records every version by design, and the lockfile carries the package's own plus
    # hundreds of others. Without this the IGNORED list could be emptied and no test would notice —
    # and every release would then refuse, on the one file that is SUPPOSED to hold old versions.
    root = _tree(tmp_path)
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [Unreleased]\n\n## [{OLD}] - 2026-01-01\n\n- something\n", encoding="utf-8"
    )
    (root / "pnpm-lock.yaml").write_text(f"lockfileVersion: '9'\nversion: {OLD}\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(root)})

    result = _run(root)

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"## [{OLD}]" in (root / "CHANGELOG.md").read_text(encoding="utf-8")
