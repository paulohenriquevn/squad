"""The routing check did not run, and said so in a line that reads as noise.

`_routing_table_path` looks for the table in `.squad/`, `rules/` and `.claude/rules/`
**relative to the registry's own directory**, and does not walk up. A monorepo whose
registry sits in `apps/<app>/BACKLOG.md` while `.claude/` is at the root therefore has
its routing silently unchecked — `WARN: routing table unreadable`, every run, on a table
that is present and parses perfectly two directories above.

The warning compounds it. `_routing()` returns `None` for three different facts:

  * `route_domain` could not be imported — the tooling is unavailable
  * no table was found in any candidate location
  * a table was found and would not parse

and all three printed *"routing table unreadable"*. An operator who can see the table,
valid, in `.claude/rules/` reads that as a false alarm, and the next real one is read the
same way. This kit's own governing defect wearing the opposite costume: not a checker
that could not measure claiming it had, but one that could not measure saying so in
terms too vague to act on.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "skills" / "backlog-review" / "scripts" / "check_backlog_structure.py"

_TABLE = ("# Domain routing\n#\n# Format:  domain | repo | agents/<specialist>.md\n#\n"
          "auth | repo-a | agents/daedalus-tech-lead.md\n")
_REGISTRY = "# Backlog\n\n## Items\n\n_None yet. Next free id: B-001._\n"


def _run(path: Path) -> str:
    done = subprocess.run([sys.executable, str(_SCRIPT), str(path)],
                          capture_output=True, text=True, timeout=120, check=False)
    return done.stdout + done.stderr


def test_the_table_is_found_from_a_registry_one_level_down(tmp_path: Path) -> None:
    """A monorepo: `.claude/` at the root, the registry under `apps/`."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "domain-routing.txt").write_text(_TABLE, encoding="utf-8")
    nested = tmp_path / "apps" / "checkout"
    nested.mkdir(parents=True)
    registry = nested / "BACKLOG.md"
    registry.write_text(_REGISTRY, encoding="utf-8")

    out = _run(registry)

    assert "routing table unreadable" not in out, (
        "the table is two directories up, present and valid, and was not found:\n" + out)


def test_a_table_beside_the_registry_still_wins(tmp_path: Path) -> None:
    """Walking up must not overtake the nearer table. A sub-project with its own
    routing is answering a different question than the umbrella's."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "domain-routing.txt").write_text(
        "# root\n#\nroot-domain | repo-r | agents/root.md\n", encoding="utf-8")
    nested = tmp_path / "apps" / "checkout"
    (nested / "rules").mkdir(parents=True)
    (nested / "rules" / "domain-routing.txt").write_text(
        "# nearer\n#\nnear-domain | repo-n | agents/near.md\n", encoding="utf-8")
    registry = nested / "BACKLOG.md"
    registry.write_text(_REGISTRY, encoding="utf-8")

    out = _run(registry)

    assert "near-domain" in out or "near.md" in out, (
        "the nearer table lost to one further up:\n" + out)
    assert "root-domain" not in out and "root.md" not in out, (
        "the umbrella's table was read instead of the sub-project's:\n" + out)


def test_a_missing_table_says_it_was_not_found(tmp_path: Path) -> None:
    """Three causes, three messages. "Unreadable" for a table that is simply absent
    sends the reader looking for a parse error that does not exist."""
    registry = tmp_path / "BACKLOG.md"
    registry.write_text(_REGISTRY, encoding="utf-8")

    out = _run(registry)

    assert "no `domain-routing.txt` found" in out, (
        "an absent table was not distinguished from an unparseable one:\n" + out)
    assert "could not be parsed" not in out, (
        "an absent table was reported as a parse failure, sending the reader to look "
        "for an error in a file that is not there:\n" + out)


def test_a_malformed_table_says_it_could_not_be_parsed(tmp_path: Path) -> None:
    """The case where "unreadable" is the truth — and it must name the file, because
    the operator's next act is to open it."""
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "domain-routing.txt").write_text("| | | |\n", encoding="utf-8")
    registry = tmp_path / "BACKLOG.md"
    registry.write_text(_REGISTRY, encoding="utf-8")

    out = _run(registry)

    assert "domain-routing.txt" in out, (
        "the warning did not name the file the operator has to open:\n" + out)
