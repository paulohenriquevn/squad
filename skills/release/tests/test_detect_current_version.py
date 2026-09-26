"""B-043 — the version base must not come from ancestry.

`skills/release/SKILL.md:67` derived it with `git describe --tags --abbrev=0`, which walks the
ANCESTRY of HEAD. In this branching model (`workspace → develop → main`) a release tag is created on
the merge commit that lands on `main`, so it is NEVER an ancestor of `workspace`. Measured here:

    git describe --tags --abbrev=0             ->  v0.52.1
    git tag --sort=-v:refname | head -1        ->  v0.64.0
    npm view @acme/tui version              ->  0.64.0
    git merge-base --is-ancestor v0.64.0 HEAD  ->  NO

Twelve versions stale, structurally — fetching does not help. A release cut from `workspace` would
compute 0.53.0, BELOW what is published, and the cycle's "tag already exists" stop condition cannot
fire because v0.53.0 was never tagged.

Every test builds a throwaway repository. Reading THIS one would make the assertions drift with each
release, which is the class of test that stops meaning anything.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import mkdtemp

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from detect_current_version import detect_current_version


def _repo(tags: list[str], manifest_version: str | None) -> Path:
    root = Path(mkdtemp(prefix="b043-"))
    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        "PATH": "/usr/bin:/bin", "HOME": str(root),
    }
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, env=env)

    git("init", "-q")
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    if manifest_version is not None:
        (root / "package.json").write_text(
            json.dumps({"name": "fixture", "version": manifest_version}), encoding="utf-8"
        )
    git("add", "-A")
    git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed")

    # Tags on a SIDE branch, never merged — the shape that defeats `git describe`, and the shape
    # this repository's release flow produces every time.
    if tags:
        git("checkout", "-q", "-b", "side")
        for tag in tags:
            (root / f"{tag}.txt").write_text(tag, encoding="utf-8")
            git("add", "-A")
            git("-c", "commit.gpgsign=false", "commit", "-q", "-m", tag)
            git("tag", "-a", tag, "-m", tag)
        git("checkout", "-q", "-")
    return root


def test_the_base_ignores_ancestry() -> None:
    # The defect itself: tags exist, none is reachable from HEAD.
    root = _repo(["v0.60.0", "v0.64.0"], "0.64.0")
    described = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=root, capture_output=True, text=True,
     check=False)
    assert described.returncode != 0 or described.stdout.strip() != "v0.64.0"

    assert detect_current_version(root) == "0.64.0"


def test_the_manifest_wins_when_it_is_ahead() -> None:
    # B-050 measured 13 published versions with NO tag, including the one npm served as `latest`.
    # A repository can be behind its own registry, so the tag alone is not the record.
    root = _repo(["v0.63.1"], "0.64.0")
    assert detect_current_version(root) == "0.64.0"


def test_the_tag_wins_when_it_is_ahead() -> None:
    # And the mirror: a manifest can lag a tag, so neither source alone is sufficient.
    root = _repo(["v0.64.0"], "0.63.1")
    assert detect_current_version(root) == "0.64.0"


def test_versions_compare_numerically_not_lexically() -> None:
    # The trap a naive fix falls into: as strings "0.9.0" > "0.10.0" is TRUE. A test written only
    # against today's single-digit numbers would not see it.
    root = _repo(["v0.9.0", "v0.10.0"], "0.9.0")
    assert detect_current_version(root) == "0.10.0"


def test_a_repository_with_no_tags_falls_back_to_the_manifest() -> None:
    root = _repo([], "0.64.0")
    assert detect_current_version(root) == "0.64.0"


def test_python_manifest_is_a_version_source() -> None:
    root = _repo([], None)
    (root / "pyproject.toml").write_text(
        '[build-system]\nrequires = []\n\n[project]\nname = "demo"\nversion = "2.3.4"\n',
        encoding="utf-8",
    )
    assert detect_current_version(root) == "2.3.4"


def test_rust_manifest_is_a_version_source() -> None:
    root = _repo([], None)
    (root / "Cargo.toml").write_text(
        '[package]\nname = "demo"\nversion = "3.4.5"\n', encoding="utf-8"
    )
    assert detect_current_version(root) == "3.4.5"


def test_a_major_disagreement_is_refused_rather_than_maximised() -> None:
    """F-1 — the review finding that overturned my own reasoning.

    I wrote that "a base that is too high is safe". It is not, and the cost is not recoverable: npm
    versions are IMMUTABLE, so a burned range is burned permanently; a major bump leaves every
    consumer's `^0.64.0` behind, so they silently stop receiving updates; and shipping 1.x is a v1.0
    claim that `rules/honesty-gate-golden-rule.md` gates and the release chain never checks.

    `git tag` has no upper bound — it lists whatever any `git fetch --tags` ever brought in.
    Measured before the guard: [v0.64.0, v1.0.0] derived 1.0.0, [v0.64.0, v9.9.9] derived 9.9.9, and
    a manifest typo of 1.64.0 derived 1.64.0.

    Within one major, disagreement is NORMAL and `max()` is right — the manifest lags the tag
    between the release commit and the merge, and the tag lags the manifest for the 13 published
    versions B-050 found with no tag. Across majors it is not normal.
    """
    import pytest

    for tags, manifest in (
        (["v0.64.0", "v1.0.0"], "0.64.0"),
        (["v0.64.0", "v9.9.9"], "0.64.0"),
        (["v0.64.0"], "1.64.0"),
    ):
        root = _repo(tags, manifest)
        with pytest.raises(SystemExit) as refused:
            detect_current_version(root)
        assert "MAJOR" in str(refused.value), (tags, manifest)


def test_no_usable_tag_and_no_manifest_refuses_rather_than_guessing_zero() -> None:
    """F-2 — the fallback reintroduced the defect this script exists to close.

    A repository with no readable version source, and no manifest, returned `0.0.0` — a base BELOW
    everything published, which is exactly what B-043 is about. The skipped-tag count was computed
    and then dropped on the floor, so the caller saw a confident answer.

    THE CASE CHANGED, THE PROPERTY DID NOT. This test used to build its "no usable tag" repository
    out of `v1.0.0-rc.1`, and in doing so it pinned the defect that
    `test_the_rc_series_advances.py` now refuses: an rc IS a version this chain cuts, and refusing
    a repository made of them stopped every project that had only ever cut pre-releases. The
    unreadable tag here is `-beta.1` — valid semver the kit does not cut and cannot order — which
    is what this refusal was always meant to be about.
    """
    import pytest

    root = _repo(["v1.0.0-beta.1"], None)
    with pytest.raises(SystemExit) as refused:
        detect_current_version(root)
    message = str(refused.value)
    assert "no semver tag and no manifest version" in message
    assert "skipped" in message
    assert "not semver" not in message, (
        "`1.0.0-beta.1` is valid semver; the kit simply does not cut it"
    )
