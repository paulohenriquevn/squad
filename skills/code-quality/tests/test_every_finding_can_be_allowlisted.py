"""The contract says every exemption goes through the allowlist. Six could not.

`is_allowlisted` requires `_detector_to_finding_type(finding.detector)` to equal the
entry's FINDING-TYPE column, and the mapping covered exactly five detector names.
Findings emitted as `d1_unavailable`, `d3_unavailable`, `d4_unavailable`,
`d3_orphan_export_skipped` and `d4_mutation_score` resolved to `""`, matched no entry a
project could write, and were structurally unallowlistable.

The direction matters: an exemption that cannot be granted is a finding a project has
to live with forever or silence some other way — which is how an allowlist stops being
the one door and becomes one of several.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "skills" / "code-quality"))

from scripts._detector_contract import (  # noqa: E402 — post-bootstrap import
    _VALID_FINDING_TYPES,
    _detector_to_finding_type,
)


#: Every `d<N>_<name>` this skill's own scripts write into a `detector=` field.
def _emitted_detector_names() -> set[str]:
    names: set[str] = set()
    for path in sorted((_ROOT / "skills" / "code-quality" / "scripts").rglob("*.py")):
        for match in re.finditer(r'detector\s*=\s*"(d\d_[a-z_]+)"',
                                 path.read_text(encoding="utf-8")):
            names.add(match.group(1))
    return names


def test_every_emitted_detector_maps_to_a_finding_type() -> None:
    unmapped = sorted(name for name in _emitted_detector_names()
                      if not _detector_to_finding_type(name))

    assert unmapped == [], (
        "these are emitted and cannot be allowlisted by any entry a project could "
        f"write: {unmapped}")


def test_every_mapping_lands_on_a_valid_finding_type() -> None:
    for name in sorted(_emitted_detector_names()):
        mapped = _detector_to_finding_type(name)
        assert mapped in _VALID_FINDING_TYPES, f"{name} -> {mapped!r}"


@pytest.mark.parametrize("detector,expected", [
    ("d1_unavailable", "dead_code"),
    ("d3_unavailable", "orphan_export"),
    ("d3_orphan_export_skipped", "orphan_export"),
    ("d4_unavailable", "mutation_low"),
    ("d4_mutation_score", "mutation_low"),
])
def test_an_unavailable_auditor_shares_its_dimension_type(detector: str, expected: str) -> None:
    """A finding about a dimension is exempted by an entry about that dimension."""
    assert _detector_to_finding_type(detector) == expected


def test_an_unknown_detector_still_maps_to_nothing() -> None:
    """The fallback stays: a name nobody emits must not silently match a type."""
    assert _detector_to_finding_type("d9_invented") == ""


# ── the two sections the template declares and the renderer omitted ──────────
#
# `templates/code-quality-report.md` declares `## Allowlist hits` (active + expired
# counts) and `## Recommended actions`; golden rule § 4 promises an expired entry is
# "listed under 'Allowlist hits — expired' in the audit report", and SKILL.md Step 3
# repeats it. `_write_markdown_report` rendered neither — the promise held in the JSON
# and nowhere a person reads.


def test_the_report_carries_every_section_the_template_declares() -> None:
    import re as _re

    template = (_ROOT / "skills" / "code-quality" / "templates"
                / "code-quality-report.md").read_text(encoding="utf-8")
    renderer = (_ROOT / "skills" / "code-quality" / "scripts"
                / "run_code_quality.py").read_text(encoding="utf-8")

    declared = _re.findall(r"^## (.+)$", template, _re.MULTILINE)
    assert declared, "the template declares no sections; this test lost its subject"

    missing = [h for h in declared if f"## {h}" not in renderer]
    assert missing == [], f"declared in the template and rendered nowhere: {missing}"


def test_recommended_actions_says_what_to_do_about_an_expired_entry() -> None:
    from scripts.run_code_quality import _recommended_actions

    text = _recommended_actions({"HARD": [], "SOFT_CAP": []},
                                {"verdict": "PASS", "expired_allowlist": ["a|b|c"]})

    assert "EXPIRED" in text
    assert "1 allowlist" in text


def test_recommended_actions_says_so_when_there_is_nothing_to_do() -> None:
    """Not an empty section: a blank heading asks whether the renderer ran."""
    from scripts.run_code_quality import _recommended_actions

    text = _recommended_actions({"HARD": [], "SOFT_CAP": []}, {"verdict": "PASS"})

    assert text.strip(), "an empty section is indistinguishable from a renderer that failed"
    assert "found nothing" in text


# ── a knob a project turns with no effect ────────────────────────────────────
#
# `rules/code-quality-thresholds.txt` documents sixteen keys as the per-project
# tuning surface. Twelve are looked up by nothing: the detector they name uses its
# built-in value, and a project setting one believes it tuned something. Worse than
# a knob that does not exist, because the belief is the whole cost.


def test_every_undocumented_knob_is_marked_as_unread() -> None:
    import re as _re

    rule = (_ROOT / "rules" / "code-quality-thresholds.txt").read_text(encoding="utf-8")
    source = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (_ROOT / "skills" / "code-quality" / "scripts").rglob("*.py"))

    documented = sorted(set(_re.findall(
        r"^#?\s*([a-z0-9_]+\.[a-z0-9_.]+)\s*=", rule, _re.MULTILINE)))
    assert documented, "no knob found; this test lost its subject"

    unmarked: list[str] = []
    for key in documented:
        read_by_code = f'"{key}"' in source
        marked_unread = f"{key} =" in rule and _re.search(
            rf"^#?\s*{_re.escape(key)}\s*=[^\n]*NOT READ", rule, _re.MULTILINE) is not None
        if not read_by_code and not marked_unread:
            unmarked.append(key)

    assert unmarked == [], (
        "these are documented as tuning knobs, read by no detector, and not marked "
        f"as such: {unmarked}")


def test_a_knob_that_is_read_is_not_marked_unread() -> None:
    """The other direction: a working knob labelled dead sends a project elsewhere."""
    import re as _re

    rule = (_ROOT / "rules" / "code-quality-thresholds.txt").read_text(encoding="utf-8")
    source = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (_ROOT / "skills" / "code-quality" / "scripts").rglob("*.py"))

    mislabelled = [
        m.group(1) for m in _re.finditer(
            r"^#?\s*([a-z0-9_]+\.[a-z0-9_.]+)\s*=[^\n]*NOT READ", rule, _re.MULTILINE)
        if f'"{m.group(1)}"' in source]

    assert mislabelled == [], f"read by a detector and marked unread: {mislabelled}"
