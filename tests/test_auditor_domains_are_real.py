"""Every domain in the auditor registry is one the detector can actually emit.

A row naming a domain `detect_domain.py` never produces is an auditor that never runs,
and nothing would say so: the review would pass with one fewer independent audit than
the registry claims to require. That is the silent-coverage failure this whole
integration exists to prevent, arriving through its own configuration file.

The reverse is deliberately NOT asserted. A domain with no auditor is a normal state —
it means no plugin in this family audits it, and the `always` row still applies.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO / "mechanisms" / "cycle"))
sys.path.insert(0, str(_REPO / "mechanisms" / "conventions"))
sys.path.insert(0, str(_REPO / "skills" / "review" / "scripts"))

from detect_domain import DOMAINS  # noqa: E402
from select_auditors import ALWAYS, parse_registry  # noqa: E402


def _registry() -> list:
    return parse_registry((_REPO / "rules" / "review-auditors.txt").read_text(encoding="utf-8"))


def test_every_declared_domain_is_one_the_detector_emits() -> None:
    known = set(DOMAINS) | {ALWAYS}
    declared = {a.domain for a in _registry()}

    unknown = sorted(declared - known)
    assert not unknown, (
        f"rules/review-auditors.txt maps {unknown}, which `detect_domain.py` never "
        f"emits. Those auditors would never be selected, and the review would pass "
        f"with fewer independent audits than the registry claims to require. Known "
        f"domains: {sorted(known)}"
    )


def test_the_always_row_exists_so_something_always_audits() -> None:
    """Without it, a change in an unmapped domain faces no independent auditor at all
    and nothing marks the absence."""
    assert any(a.domain == ALWAYS for a in _registry())


def test_no_plugin_is_declared_with_two_different_diff_modes() -> None:
    """The mode is the plugin's own declaration. Two rows disagreeing about one plugin
    would make the recorded scope depend on which domain happened to select it — and
    the record is what stops a scoped audit reading as a full one."""
    modes: dict[str, set[str]] = {}
    for a in _registry():
        modes.setdefault(a.plugin, set()).add(a.diff_mode)

    conflicting = {p: sorted(m) for p, m in modes.items() if len(m) > 1}
    assert not conflicting, f"one plugin, two declared diff modes: {conflicting}"


def test_every_auditor_writes_inside_the_write_root() -> None:
    """The report location is derived, so two rows cannot disagree about it.

    This test replaced one that checked exactly that disagreement. The column is gone:
    each plugin's own default (`security-output/`, `code-review-output/`) put a third
    party's output at the project root — outside the one write root, on this kit's
    instruction. A tool the kit tells where to write is a tool the kit is responsible
    for.
    """
    from pathlib import Path

    from squad.paths import contains

    project = Path("/tmp/some-project")
    for auditor in _registry():
        target = auditor.output_dir(project)
        assert contains(project, target), f"{auditor.plugin} writes to {target}"
        assert auditor.plugin in target.parts, target
