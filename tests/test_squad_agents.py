"""The squad's four agents, and the three files that each name all four.

`install.sh` is the single source — `tests/kit_agents.py` reads the list out of the
copy loop rather than restating it. But two more places carry the same fact and
cannot read a Python helper: the files on disk under `agents/`, and the `.gitignore`
exceptions that keep them versioned while every domain specialist stays out.

Three copies of one fact is three chances to drift, and the drift is silent in the
worst direction: an agent added to `install.sh` and not to `.gitignore` is copied to
consumers from a working tree and never committed, so it exists on one machine — the
exact failure `agents/README.md` records for the eight specialists that lived on one
disk for months.

The `.gitignore` half is not hypothetical. The paragraph explaining why the kit's
agents are an exception sat in the file with **no rule under it**: nothing ignored
`agents/`, so a scaffolded specialist was tracked and one `git add -A` from shipping.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # for kit_agents
from kit_agents import kit_agents  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"


def _agent_files() -> set[str]:
    return {p.name for p in AGENTS.glob("*.md")}


def _ignored(path: str) -> bool:
    return subprocess.run(["git", "check-ignore", "-q", path],
                          cwd=ROOT).returncode == 0


# ── the three lists agree ─────────────────────────────────────────────────────


def test_every_agent_the_installer_copies_exists_on_disk() -> None:
    missing = kit_agents() - _agent_files()
    assert missing == set(), f"install.sh copies files that do not exist: {sorted(missing)}"


def test_every_agent_on_disk_is_copied_by_the_installer() -> None:
    """The other direction, and the one that fails quietly: an agent nobody installs
    reaches no consumer, so its doctrine applies to this repository alone."""
    orphaned = _agent_files() - kit_agents()
    assert orphaned == set(), f"agents/ holds files install.sh never copies: {sorted(orphaned)}"


def test_every_kit_agent_is_excepted_from_the_gitignore() -> None:
    for name in sorted(kit_agents()):
        assert not _ignored(f"agents/{name}"), (
            f"agents/{name} is ignored — install.sh copies it, so it would ship from a "
            f"working tree and exist on one machine only")


def test_a_domain_specialist_is_ignored() -> None:
    """The rule the exceptions are exceptions TO. Without it the exceptions are
    decoration and every scaffolded specialist is stageable."""
    assert _ignored("agents/some-project-domain.md"), (
        "agents/ is not ignored — a specialist scaffolded here would be committed, "
        "which is what makes a consumer's routing gate refuse every item they file")


# ── each agent is a real agent ────────────────────────────────────────────────


def test_every_agent_declares_the_name_its_filename_promises() -> None:
    """`claude -p` resolves an agent by the `name:` in its frontmatter, and
    `install.sh` copies it by filename. A file whose two names disagree installs
    fine and answers to nobody."""
    for name in sorted(kit_agents() - {"README.md"}):
        body = (AGENTS / name).read_text(encoding="utf-8")
        assert body.startswith("---\n"), f"{name} has no frontmatter"
        front = body.split("---", 2)[1]
        declared = next(
            (ln.split(":", 1)[1].strip() for ln in front.splitlines()
             if ln.startswith("name:")), None)
        assert declared == name[:-3], (
            f"{name} declares name={declared!r}; `claude -p` will not find it")


def test_every_agent_names_the_other_three() -> None:
    """The seams are the design: each file carries the four-role table so a reader
    who opens one learns where its authority ends. A role that could do two of these
    is a role that can overrule itself."""
    squad = sorted(kit_agents() - {"README.md"})
    for name in squad:
        body = (AGENTS / name).read_text(encoding="utf-8")
        for other in squad:
            assert other[:-3] in body, f"{name} never mentions {other[:-3]}"


def test_the_tech_lead_delegates_through_the_router() -> None:
    """Developers and QA are the project's own domain specialists, not shipped ones.
    The Tech Lead's delegation has to be mechanical — `route_domain.py` and its exit
    codes — or it is a paragraph asking politely."""
    body = (AGENTS / "daedalus-tech-lead.md").read_text(encoding="utf-8")

    assert "route_domain.py" in body
    assert "BROKEN ROUTE" in body, "exit 3 is the case that tests the role"
    assert (ROOT / "scripts" / "route_domain.py").is_file()


def test_the_readme_table_lists_exactly_the_squad() -> None:
    readme = (AGENTS / "README.md").read_text(encoding="utf-8")
    for name in sorted(kit_agents() - {"README.md"}):
        assert name[:-3] in readme, f"agents/README.md does not list {name[:-3]}"
