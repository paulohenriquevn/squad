"""Every reviewer was told to write where nothing reads.

The templates say:

    Save to `.claude/agents/review-{SLUG}-{DATE}/findings/architecture.yml`

`{SLUG}` and `{DATE}` are substituted, so the instruction resolves to a real path — just
not the one `spawn_reviewers` creates. The script writes:

    findings_dir = output_dir / "findings"

and `output_dir` is under `.squad/records/reviews/…`. The consolidator is then pointed at
that directory with `--findings-dir`, so a reviewer that followed its own brief left its
findings somewhere the consolidation never looks.

Measured on a consumer 2026-09-18: **all eleven reviewers** needed the path corrected by
hand in their dispatch prompt. Nothing failed loudly — a reviewer writes the file, the
consolidator finds an empty directory, and the review reports on the findings it could
see, which were none.

The fix is a placeholder rather than a corrected literal. A second hand-written copy of
the path in eleven templates is what produced this, and correcting all eleven leaves the
twelfth to be written wrong.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_TEMPLATES = sorted(
    (Path(__file__).resolve().parents[1] / "templates").glob("agent-*.md"))


def test_there_are_templates_to_check() -> None:
    """Non-vacuity floor: a glob that stopped matching would pass every case below."""
    assert _TEMPLATES, "no agent templates found; this test needs re-pointing"


@pytest.mark.parametrize("template", _TEMPLATES, ids=lambda p: p.stem)
def test_a_template_does_not_hardcode_the_findings_path(template: Path) -> None:
    """The path belongs to `spawn_reviewers`, which creates it."""
    body = template.read_text(encoding="utf-8")

    stale = re.findall(r"`?\.claude/agents/review-\{SLUG\}[^`\s]*`?", body)
    assert not stale, (
        f"{template.name} tells its reviewer to write to {stale[0]} — the consolidator "
        f"reads `output_dir/findings`, under the write root. Use `{{FINDINGS_DIR}}`, "
        f"which the script fills with the directory it actually creates")


@pytest.mark.parametrize("template", _TEMPLATES, ids=lambda p: p.stem)
def test_a_template_that_names_a_findings_file_uses_the_placeholder(template: Path) -> None:
    """Whatever it is called, it must come from the script."""
    body = template.read_text(encoding="utf-8")
    if "findings/" not in body and "FINDINGS_DIR" not in body:
        pytest.skip("this template does not tell the reviewer to write findings")

    assert "{FINDINGS_DIR}" in body, (
        f"{template.name} names a findings file without the placeholder, so the path "
        f"is a second copy of something only `spawn_reviewers` knows")


def test_the_script_supplies_the_placeholder() -> None:
    """The other half: a placeholder nothing fills renders literally into the brief."""
    script = (Path(__file__).resolve().parents[1] / "scripts"
              / "spawn_reviewers.py").read_text(encoding="utf-8")

    assert '"FINDINGS_DIR"' in script, (
        "the templates ask for {FINDINGS_DIR} and the mapping does not provide it — "
        "every reviewer would read the marker verbatim")
