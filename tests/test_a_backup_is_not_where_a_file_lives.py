"""The checker resolved a citation against `.install-backups/` and named it as the location.

`check_xrefs` already knows a backup is not part of the tree. The markdown-link walk at
`:349` skips it, with the reason written above the line:

    `.install-backups/` holds the PREVIOUS install, snapshotted by `install.sh --force`
    before it replaced anything. [...] A backup of an old ecosystem is not this ecosystem.

Two other passes in the same file search the whole tree and do not apply it:
`_resolve_cited_doc` (`:432`) and the `bare_rule_name_resolves` check (`:1060`). Measured
2026-09-22 against a real install by the session that maintains it:

    [WARN] bare_rule_name_resolves: rules/README.md cites `domain-routing.txt` as if it
    were in rules/; the file is in .install-backups/20260829T121853/rules/

The file is NOT there in any sense a reader can act on — that directory is a snapshot of
what the install looked like before the last upgrade. The citation does not resolve, and
the message says it resolves somewhere else, which is the worse of the two answers: it
sends the reader into a backup and reads as *your pointer is misfiled* rather than *this
file is gone*.

The rule was written once and applied to one of three readers. That is the shape this kit
keeps finding in itself, and the fix is the shape too: one predicate, used by all three.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
CHECKER = _ROOT / "mechanisms" / "gates" / "check_xrefs.py"

sys.path.insert(0, str(_ROOT / "mechanisms" / "gates"))


def _eco(tmp_path: Path) -> Path:
    """An ecosystem whose only copy of a cited rule sits in a backup."""
    eco = tmp_path / ".claude"
    (eco / "rules").mkdir(parents=True)
    backup = eco / ".install-backups" / "20260829T121853" / "rules"
    backup.mkdir(parents=True)
    (backup / "domain-routing.txt").write_text("# the previous install\n", encoding="utf-8")
    (eco / "rules" / "README.md").write_text(
        "# Rules\n\nThe routing table lives in `domain-routing.txt`.\n", encoding="utf-8")
    return eco


def test_a_backup_is_not_a_location_the_checker_offers() -> None:
    from check_xrefs import is_excluded_tree

    assert is_excluded_tree(Path(".install-backups/20260829T121853/rules/x.txt"))
    assert is_excluded_tree(Path(".patch-backups/rules/x.txt"))
    assert is_excluded_tree(Path("skills/x/__pycache__/y.pyc"))


def test_a_real_path_is_not_excluded() -> None:
    """THE CONTROL. An exclusion that swallows the tree reports nothing and passes."""
    from check_xrefs import is_excluded_tree

    assert not is_excluded_tree(Path("rules/domain-routing.txt"))
    assert not is_excluded_tree(Path("skills/backlog-init/SKILL.md"))
    # The word appearing INSIDE a name is not the directory.
    assert not is_excluded_tree(Path("rules/a-policy-about-backups.md"))


def test_the_resolver_does_not_return_a_file_from_a_backup(tmp_path: Path) -> None:
    from check_xrefs import _resolve_cited_doc

    eco = _eco(tmp_path)

    assert _resolve_cited_doc("domain-routing.txt", eco / "rules" / "README.md", eco) is None


def test_the_report_does_not_send_a_reader_into_a_backup(tmp_path: Path) -> None:
    """End to end: whatever the checker says, it must not name that directory."""
    eco = _eco(tmp_path)

    out = subprocess.run([sys.executable, str(CHECKER), "--root", str(eco)],
                         capture_output=True, text=True, check=False)

    assert ".install-backups" not in out.stdout, out.stdout
