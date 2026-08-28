"""A file's name is the first documentation anyone reads.

WHY THIS GATE EXISTS
--------------------
`~/.claude/CLAUDE.md` § 5 makes it a rule of the house — quoted verbatim below,
in the language it is written in:  <!-- english-only: verbatim quotation -->
*"Escolha sempre o nome  <!-- english-only: verbatim quote of CLAUDE.md -->
mais específico e descritivo. Melhor um nome longo e claro do que um nome curto
e problemático."* It names the anti-pattern too — *"Classes 'Manager', 'Helper'
ou 'Utils' que viram lixeira de métodos sem relação"* — and the same failure
applies to a directory: `lib/` tells the reader nothing except that someone had
files left over.

Measured across both kits before this gate existed: `hooks/lib/`,
`skills/quality-init/scripts/lib/`, a `helpers.py`, a `scripts/` mixing
kebab-case and snake_case with no rule, and four `test_*.py` living outside any
test directory.

WHAT IT CHECKS, AND WHY EACH IS MECHANIZABLE
---------------------------------------------
| Finding | Why a script can decide it |
|---|---|
| `dumping_ground_name` | closed list of words that name a leftover, not a purpose |
| `mixed_naming_convention` | one directory, both `-` and `_`, is a fact |
| `test_outside_test_dir` | `test_*.py` outside a test tree is misfiled by definition |
| `purpose_not_stated` | an executable with no docstring says nothing at all |

WHAT IT CANNOT DECIDE
---------------------
Whether `trajectory-review` is a better name than `trajectory-validation`. That is
judgement about meaning, and a checker asserting it would produce confident
nonsense. The gate catches names that are *structurally* empty; a human still
has to notice that a name is merely vague.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_semantic_names import check_semantic_names  # noqa: E402


def _repo(tmp_path: Path, *relative: str) -> Path:
    for item in relative:
        path = tmp_path / item
        if item.endswith("/"):
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('#!/usr/bin/env python3\n"""Does a stated thing."""\n', encoding="utf-8")
    return tmp_path


def _kinds(report) -> list[str]:
    return sorted({f.kind for f in report.findings})


# ---------------------------------------------------------------------------
# Dumping-ground names
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["lib", "utils", "helpers", "misc", "common", "stuff"])
def test_a_dumping_ground_directory_is_reported(tmp_path: Path, name: str) -> None:
    root = _repo(tmp_path, f"scripts/{name}/thing.py")

    report = check_semantic_names(root)

    assert "dumping_ground_name" in _kinds(report)
    assert name in report.findings[0].path


def test_a_dumping_ground_filename_is_reported(tmp_path: Path) -> None:
    root = _repo(tmp_path, "tests/helpers.py")

    assert "dumping_ground_name" in _kinds(check_semantic_names(root))


def test_a_language_mandated_name_is_not_a_finding(tmp_path: Path) -> None:
    """`__init__.py` and `conftest.py` are fixed by Python and pytest. Reporting
    them would be reporting the language, and a gate that fires on something
    nobody can change is a gate people learn to ignore."""
    root = _repo(tmp_path, "scripts/pack/__init__.py", "conftest.py")

    assert check_semantic_names(root).findings == []


def test_vendored_third_party_code_is_not_ours_to_name(tmp_path: Path) -> None:
    """A directory carrying its own LICENSE came from somewhere else.

    Renaming a file inside it breaks the comparison with upstream and quietly
    detaches the attribution from what it covers. `skill-creator` and
    `frontend-design` are the real cases here, both MIT with their licence
    shipped alongside.
    """
    root = _repo(tmp_path, "skills/vendored/scripts/utils.py")
    (tmp_path / "skills" / "vendored" / "LICENSE.txt").write_text("MIT", encoding="utf-8")

    assert check_semantic_names(root).findings == []


def test_our_own_code_next_to_a_vendored_tree_is_still_checked(tmp_path: Path) -> None:
    """The exemption is the licensed directory, not everything near it."""
    root = _repo(tmp_path, "skills/vendored/scripts/utils.py", "scripts/helpers.py")
    (tmp_path / "skills" / "vendored" / "LICENSE.txt").write_text("MIT", encoding="utf-8")

    findings = check_semantic_names(root).findings

    assert len(findings) == 1
    assert "scripts/helpers.py" in findings[0].path


def test_a_word_that_merely_contains_a_banned_one_is_not_a_finding(tmp_path: Path) -> None:
    """`library-audit.py` is a purpose; `lib/` is a leftover. Substring matching
    would fail the first for containing the second."""
    root = _repo(tmp_path, "scripts/library-audit.py", "skills/common-crawl/SKILL.md")

    assert check_semantic_names(root).findings == []


# ---------------------------------------------------------------------------
# One convention per directory
# ---------------------------------------------------------------------------

def test_kebab_and_snake_in_one_directory_is_reported(tmp_path: Path) -> None:
    """Two conventions in one folder means the reader guesses which applies, and
    the next author copies whichever file they opened first."""
    root = _repo(tmp_path, "scripts/check_xrefs.py", "scripts/generate-settings.py")

    report = check_semantic_names(root)

    assert "mixed_naming_convention" in _kinds(report)
    detail = next(f.detail for f in report.findings if f.kind == "mixed_naming_convention")
    assert "check_xrefs.py" in detail or "generate-settings.py" in detail


def test_one_convention_per_directory_passes(tmp_path: Path) -> None:
    root = _repo(tmp_path, "scripts/check_xrefs.py", "scripts/route_domain.py")

    assert "mixed_naming_convention" not in _kinds(check_semantic_names(root))


def test_separate_directories_may_differ(tmp_path: Path) -> None:
    """The rule is one convention per directory, not one per repository — hooks
    are shell and use kebab by long habit; Python modules cannot."""
    root = _repo(tmp_path, "scripts/route_domain.py", "hooks/post-edit-check.sh")

    assert "mixed_naming_convention" not in _kinds(check_semantic_names(root))


# ---------------------------------------------------------------------------
# Tests live in test directories
# ---------------------------------------------------------------------------

def test_a_test_outside_a_test_directory_is_reported(tmp_path: Path) -> None:
    """A `test_*.py` under `scripts/` is collected by a pytest run nobody
    intended, or missed by the one they did."""
    root = _repo(tmp_path, "scripts/test_something.py")

    assert "test_outside_test_dir" in _kinds(check_semantic_names(root))


@pytest.mark.parametrize("where", ["tests/test_a.py", "skills/demo/tests/test_b.py"])
def test_a_test_inside_a_test_directory_passes(tmp_path: Path, where: str) -> None:
    root = _repo(tmp_path, where)

    assert "test_outside_test_dir" not in _kinds(check_semantic_names(root))


# ---------------------------------------------------------------------------
# The purpose is stated somewhere
# ---------------------------------------------------------------------------

def test_an_executable_with_no_stated_purpose_is_reported(tmp_path: Path) -> None:
    """When the name cannot carry the whole purpose, the file must. A script
    with neither is a file whose reason for existing lives only in whoever
    wrote it."""
    path = tmp_path / "scripts" / "attest-plan.sh"
    path.parent.mkdir(parents=True)
    path.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho hi\n", encoding="utf-8")

    assert "purpose_not_stated" in _kinds(check_semantic_names(tmp_path))


def test_a_shell_script_stating_its_purpose_in_a_header_comment_passes(tmp_path: Path) -> None:
    path = tmp_path / "scripts" / "install.sh"
    path.parent.mkdir(parents=True)
    path.write_text(
        "#!/usr/bin/env bash\n# Install the kit into a consumer project.\nset -eu\n",
        encoding="utf-8",
    )

    assert "purpose_not_stated" not in _kinds(check_semantic_names(tmp_path))


def test_a_python_module_with_a_docstring_passes(tmp_path: Path) -> None:
    root = _repo(tmp_path, "scripts/route_domain.py")

    assert "purpose_not_stated" not in _kinds(check_semantic_names(root))


# ---------------------------------------------------------------------------
# Sweep and reporting
# ---------------------------------------------------------------------------

def test_the_report_counts_what_it_inspected(tmp_path: Path) -> None:
    root = _repo(tmp_path, "scripts/route_domain.py", "scripts/check_xrefs.py")

    report = check_semantic_names(root)

    assert report.paths_read == 2
    assert report.directories_read >= 1


def test_vendored_and_generated_trees_are_skipped(tmp_path: Path) -> None:
    """`node_modules/` and `.git/` are not ours to name."""
    root = _repo(tmp_path, "node_modules/pkg/lib/index.js", ".venv/lib/thing.py")

    assert check_semantic_names(root).findings == []


def test_the_cli_exits_nonzero_on_a_finding(tmp_path: Path) -> None:
    import subprocess

    _repo(tmp_path, "scripts/utils/thing.py")

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_semantic_names.py"),
         "--repo-root", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 1
    assert "dumping_ground_name" in result.stdout


def test_this_repository_names_everything_for_its_purpose() -> None:
    """The gate turned on its own tree. Left failing, it is a rule the kit
    demands of consumers and does not keep."""
    report = check_semantic_names(REPO_ROOT)

    assert report.findings == [], "\n".join(
        f"[{f.kind}] {f.path}: {f.detail}" for f in report.findings
    )
