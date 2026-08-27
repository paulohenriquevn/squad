"""D1 audits the PRODUCT, not the kit installed inside it.

THE DEFECT THIS CLOSES
----------------------
`_shared.DEFAULT_SKIP_DIRS` has carried `.claude` since it was written, with the
comment stating the intent outright:

    ".claude",  # meta-tooling — /code-quality audits the PRODUCT, not its own skills

`enumerate_source_files` honours it. D1 does not: it hands `manifest_dir` to
vulture and lets vulture walk everything below it.

Measured 2026-08-27 in a freshly installed demo project — three source files of
its own, the kit under `.claude/` — at `vulture.min_confidence = 60`:

    44 findings: 38 in .claude/skills, 4 in .claude/scripts, 2 in src/billing

So 42 of 44 were about code the adopter never wrote, and the verdict was
`FAIL_HARD` on their strength. It is the same defect the stop-hook had and the
CHANGELOG records fixing — *"107 lines of warning about `.claude/skills/**/*.py`
against ONE real finding"* — never propagated to this gate.

Auditing your own dependency is the canonical way to teach someone to ignore the
gate, and an ignored gate protects nothing.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts.detectors.python import PythonDetector


def _project_with_installed_kit(root: Path) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text(
        "def _dead_in_the_product(x):\n    unused = 1\n    return x\n", encoding="utf-8")
    kit = root / ".claude" / "skills" / "demo" / "scripts"
    kit.mkdir(parents=True)
    (kit / "tool.py").write_text(
        "def _dead_in_the_kit(y):\n    unused_too = 2\n    return y\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    return root


@pytest.mark.skipif(shutil.which("vulture") is None, reason="vulture not installed")
def test_findings_come_from_the_product_and_not_from_the_installed_kit(tmp_path: Path) -> None:
    root = _project_with_installed_kit(tmp_path)

    findings = PythonDetector(min_confidence=60).detect_dead_code(root)

    files = {f.file_path for f in findings}
    assert not any(".claude" in path for path in files), (
        f"the gate audited its own installation: {sorted(files)}"
    )
    assert any("app.py" in path for path in files), (
        "excluding the kit must not blind the detector to the product"
    )


@pytest.mark.skipif(shutil.which("vulture") is None, reason="vulture not installed")
def test_the_standalone_repo_still_audits_its_own_scripts(tmp_path: Path) -> None:
    """The exclusion is about `.claude/` as an INSTALL, not about the kit's own
    tree. In the standalone layout the scripts ARE the product, and skipping them
    would silence the gate exactly where the kit self-hosts."""
    for part in ("skills", "rules", "hooks"):
        (tmp_path / part).mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "tool.py").write_text(
        "def _dead(z):\n    unused = 3\n    return z\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='kit'\n", encoding="utf-8")

    findings = PythonDetector(min_confidence=60).detect_dead_code(tmp_path)

    assert any("tool.py" in f.file_path for f in findings)
