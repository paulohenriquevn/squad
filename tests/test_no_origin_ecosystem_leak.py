"""The consumer does not inherit another ecosystem's repository map.

THE DEFECT THIS FIXES
---------------------
`rules/cycle-backlog.md` carries the per-domain routing table, and the version
versioned here was once the origin ecosystem's: eight domains pointing at
`theo-cloud`, `theo-rag`, `theo-contracts` and twelve more repositories.

The file itself already described the consequence, with a measurement:

    "A consumer that keeps this table inherits a map of repos it does not have,
     and gate G1 then refuses every item it files. Measured on `theokit-sdk`
     (2026-08-18): 88 items with measured file:line evidence, all
     BLOCKER/unroutable_repo."

Knowing and shipping anyway is the part this test ends. `install.sh` already
preserved a consumer's DERIVED table in `--merge` mode; what was missing was the
clean-install case, where there is no previous table to preserve and the origin
ecosystem's went out by default.

WHY THE TEST MEASURES THE INSTALL, NOT THE REPOSITORY
------------------------------------------------------
A repository's table is correct FOR IT — whoever derived it really maintains those
repos, and `route_domain.py` depends on it to run there. The defect was never
having it; it was shipping it. So the assertion is about what leaves the
installer, and each repository stays free to describe its own ecosystem.

This repository stopped exercising that freedom on 2026-08-26: the table and the eight
specialists it named left, and the section began being born empty in the source
too. The test still holds, and is still what guarantees the property — the source
may go back to describing an ecosystem at any moment, and the shipped copy may
not.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Names that only make sense in the origin ecosystem. Deliberately specific:
#: `control-plane` or `engine-go` on their own are generic terms a consumer may
#: legitimately use as a domain name of their own.
ORIGIN_MARKERS = (
    "theo-cloud",
    "theo-rag",
    "theo-memory",
    "theo-lens",
    "theo-trust",
    "theo-skills",
    "theo-promptly",
    "theo-contracts",
    "theo-infra-modules",
    "theo-infra-live",
    "theo-traefik-mcp",
    "theo-cli",
    "theo-storage",
    "usetheo.dev",
    "@usetheo/",
)


@pytest.fixture(scope="module")
def installed_rules(versioned_kit: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("consumer")
    proc = subprocess.run(  # noqa: PLW1510
        ["bash", str(versioned_kit / "scripts" / "install.sh"), str(target)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return target / ".claude" / "rules"


def _leaks(text: str) -> list[str]:
    return sorted({m for m in ORIGIN_MARKERS if m in text})


def test_routing_table_ships_empty(installed_rules: Path):
    """A clean install must not name another ecosystem's repositories."""
    backlog = installed_rules / "cycle-backlog.md"
    assert backlog.is_file()
    found = _leaks(backlog.read_text(encoding="utf-8"))
    assert not found, (
        f"the shipped cycle-backlog.md names origin-ecosystem repositories: {found}. "
        "Every item the consumer files will be refused by G1 as unroutable_repo."
    )


def test_routing_table_still_tells_the_consumer_what_to_do(installed_rules: Path):
    """Emptying without instructing merely trades one failure for another.

    The section must still exist and point at the command that derives it —
    otherwise the consumer finds a void without knowing they are the one to fill it.
    """
    body = (installed_rules / "cycle-backlog.md").read_text(encoding="utf-8")
    section = re.search(r"^##\s+Domain routing\b.*?(?=^##\s|\Z)", body, re.MULTILINE | re.DOTALL)
    assert section, "the `## Domain routing` section vanished from the shipped file"
    assert "detect_domains.py" in section.group(0), (
        "the section does not name the script that derives the table for the project"
    )


@pytest.mark.parametrize("name", ["live-target.txt", "acceptance-target.txt"])
def test_target_declarations_ship_undeclared(installed_rules: Path, name: str):
    """Um alvo herdado faz o kit sondar o produto de outra pessoa.

    `/discover-execute` in live-test mode and `/acceptance` exercise what these
    files declare. Inheriting the origin declaration is not just noise: it produces
    "evidence" about a system that is not the consumer's.
    """
    found = _leaks((installed_rules / name).read_text(encoding="utf-8"))
    assert not found, f"{name} entregue cita o ecossistema de origem: {found}"


def test_every_shipped_config_file_is_clean(installed_rules: Path):
    """A sweep over ALL shipped configuration, not only the known files.

    Um `rules/*.txt` novo criado depois deste teste entra na varredura sozinho —
    that is the difference between a test that pins today's list and one that pins the rule.
    """
    dirty = {
        p.name: _leaks(p.read_text(encoding="utf-8", errors="replace"))
        for p in sorted(installed_rules.glob("*.txt"))
    }
    dirty = {k: v for k, v in dirty.items() if v}
    assert not dirty, f"shipped configuration citing the origin ecosystem: {dirty}"
