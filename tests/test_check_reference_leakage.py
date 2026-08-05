"""Tests for scripts/check_reference_leakage.py.

Behaviour under test: a literal copy of study material into the project is
detected; independent code is not; and an absent zone degrades to SKIP instead of
a false PASS.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_reference_leakage.py"

COPIED_BLOCK = """\
def dict_expand_if_needed(d):
    if d.rehash_idx != -1:
        return OK
    if d.table_size == 0:
        return dict_expand(d, DICT_INITIAL_SIZE)
    if d.used >= d.table_size and dict_can_resize:
        return dict_expand(d, d.used + 1)
    return OK
"""

INDEPENDENT_BLOCK = """\
def compute_invoice_total(items, tax_rate):
    subtotal = sum(item.price * item.quantity for item in items)
    discount = subtotal * 0.1 if subtotal > 1000 else 0
    taxable = subtotal - discount
    return round(taxable * (1 + tax_rate), 2)
"""


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "proj"
    (repo / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "workspace", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


def _add_zone_file(repo: Path, relative: str, content: str) -> None:
    path = repo / "knowledge-base" / "references" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run(repo: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), *extra],
        capture_output=True,
        text=True,
    )


def test_literal_copy_from_zone_is_detected(tmp_path):
    repo = _init_repo(tmp_path)
    _add_zone_file(repo, "redis/dict.py", COPIED_BLOCK)
    (repo / "src" / "mine.py").write_text(COPIED_BLOCK, encoding="utf-8")

    result = _run(repo, "--strict")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "SUSPECTED COPY" in result.stderr
    assert "src/mine.py" in result.stderr
    assert "redis/dict.py" in result.stderr


def test_independent_code_is_not_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _add_zone_file(repo, "redis/dict.py", COPIED_BLOCK)
    (repo / "src" / "mine.py").write_text(INDEPENDENT_BLOCK, encoding="utf-8")

    result = _run(repo, "--strict")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_absent_zone_skips_instead_of_passing(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "src" / "mine.py").write_text(COPIED_BLOCK, encoding="utf-8")

    result = _run(repo, "--strict")

    assert result.returncode == 0
    assert "SKIP" in result.stdout
    assert "PASS" not in result.stdout


def test_copy_is_detected_despite_whitespace_and_case_changes(tmp_path):
    """Reindenting or re-casing a paste must not defeat detection."""
    repo = _init_repo(tmp_path)
    _add_zone_file(repo, "redis/dict.py", COPIED_BLOCK)
    disguised = "\n".join("    " + line.upper() for line in COPIED_BLOCK.splitlines())
    (repo / "src" / "mine.py").write_text(disguised, encoding="utf-8")

    result = _run(repo, "--strict")

    assert result.returncode == 1, result.stdout + result.stderr


def test_short_shared_snippet_below_shingle_size_is_not_flagged(tmp_path):
    """Two or three shared lines are boilerplate, not provenance."""
    repo = _init_repo(tmp_path)
    _add_zone_file(repo, "redis/dict.py", COPIED_BLOCK)
    (repo / "src" / "mine.py").write_text(
        "def dict_expand_if_needed(d):\n    if d.rehash_idx != -1:\n        return OK\n",
        encoding="utf-8",
    )

    result = _run(repo, "--strict")

    assert result.returncode == 0, result.stdout + result.stderr


def test_truncation_is_reported_never_silent(tmp_path):
    repo = _init_repo(tmp_path)
    for i in range(3):
        _add_zone_file(repo, f"peer/file{i}.py", COPIED_BLOCK)
    (repo / "src" / "mine.py").write_text(INDEPENDENT_BLOCK, encoding="utf-8")

    result = _run(repo, "--max-zone-files", "1")

    assert "Coverage is PARTIAL" in result.stderr
    assert "scanned only 1 of 3" in result.stderr


def test_zone_file_is_not_compared_against_itself(tmp_path):
    """The zone is excluded from the changed-file index — otherwise every zone
    file would trivially match itself and the check would be pure noise."""
    repo = _init_repo(tmp_path)
    _add_zone_file(repo, "redis/dict.py", COPIED_BLOCK)

    result = _run(repo, "--strict")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "SUSPECTED COPY" not in result.stderr


@pytest.mark.parametrize("bad", ["0", "1"])
def test_invalid_shingle_size_is_an_invocation_error(tmp_path, bad):
    repo = _init_repo(tmp_path)
    result = _run(repo, "--shingle", bad)
    assert result.returncode == 2
    assert "ERROR" in result.stderr
