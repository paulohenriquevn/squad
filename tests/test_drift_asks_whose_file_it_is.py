"""Six of a consumer's own configured files were reported as needing a human.

`squad/boundaries.py` declares `rules/*.txt`, `agents/` and `settings.json` as
PROJECT_OWNED, and says why: "a consumer tunes these and the installer preserves them
across an update." `check_install_drift` did not ask, and on a real consumer 2026-09-16
it reported all six as DIVERGED or INSTALL_AHEAD — its language table, its allowlist,
its domain routing, its acceptance target. **A difference in those is the system
working.**

An alarm that fires on the normal case is an alarm people scroll past, which is this
kit's own sentence about a different gate.

And the summary named a class that was empty: "DIVERGED files need a human" printed on
runs with zero diverged files, because three conditions shared one message. It now names
whichever fired.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "mechanisms" / "gates"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_install_drift import (  # noqa: E402 — post-bootstrap import
    Drift,
    classify_file,
)


def _pair(tmp_path: Path, rel: str, install: str, kit: str) -> tuple[Path, Path]:
    a, b = tmp_path / "install.txt", tmp_path / "kit.txt"
    a.write_text(install, encoding="utf-8")
    b.write_text(kit, encoding="utf-8")
    return a, b


def test_a_tuned_rule_file_is_not_drift(tmp_path: Path) -> None:
    a, b = _pair(tmp_path, "", "go | go.mod | ENABLED\n", "# nothing enabled\n")
    assert classify_file(a, b, rel="rules/code-quality-languages.txt") is Drift.YOURS


def test_the_measured_project_owned_shapes_are_recognised(tmp_path: Path) -> None:
    a, b = _pair(tmp_path, "", "mine\n", "theirs\n")
    for rel in ("rules/anything.txt", "settings.json", ".kit-manifest.txt"):
        assert classify_file(a, b, rel=rel) is Drift.YOURS, rel


def test_agents_is_left_exactly_as_it_was(tmp_path: Path) -> None:
    """Three mechanisms disagree about `agents/` and this gate does not break the tie.

    `boundaries.PROJECT_OWNED` calls the whole directory the consumer's.
    `test_install_drift_scope` asserts `agents/README.md` is the kit's, because it
    describes the routing mechanism. `install.sh` says why both are right — the
    directory carries the kit's four roles AND the project's specialists — with the
    MANIFEST as the discriminator, which `is_project_owned` consults for `skills/` and
    not for `agents/`.

    Which reader should change is a decision about the ownership contract. Resolving it
    from inside a drift gate would be a fourth reader inventing an answer, so this
    narrows to the six `rules/*.txt` files a real consumer had tuned and leaves `agents/`
    classified exactly as before.
    """
    a, b = _pair(tmp_path, "", "mine\n", "theirs\n")
    assert classify_file(a, b, rel="agents/README.md") is not Drift.YOURS
    assert classify_file(a, b, rel="agents/specialist.md") is not Drift.YOURS


def test_a_kit_file_is_still_classified(tmp_path: Path) -> None:
    """The fix must not turn every difference into 'yours'."""
    a, b = _pair(tmp_path, "", "mine\n", "theirs\n")
    assert classify_file(a, b, rel="mechanisms/gates/check_xrefs.py") is Drift.DIVERGED


def test_the_summary_names_the_class_that_fired(tmp_path: Path) -> None:
    """Three conditions shared one message, so a run with zero diverged files still
    told the reader to go resolve a conflict."""
    source = (_ROOT / "mechanisms" / "gates"
              / "check_install_drift.py").read_text(encoding="utf-8")
    assert 'why.append' in source, "the summary is still one fixed sentence"
    assert '"\\ncheck-install-drift: " + "; ".join(why)' in source
