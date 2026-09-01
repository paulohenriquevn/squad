"""An index is the one document nothing forces you to open when you add a file.

So it drifts by default, and the drift is invisible: the file still reads as
complete. This one drifted twice. The CHANGELOG records the second time —
*"the old `README.md` under `skills/`: it said 35 skills, there are 36, and the table omitted 7"* —
and notes that four of the omitted skills had **zero mentions in any entry point**:
on disk, passing every validator, unreachable by any discovery path.

When `map.md` replaced it on 2026-08-31 the same file claimed 36 against 34 on
disk and listed 29. Among the five missing was `shared-understanding` (renamed
`plan-alignment` later the same day), the
alignment gate that is unbreakable for every item coming from `BACKLOG.md`.

Twice is a pattern. These tests are the third time not happening.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_skill_map import check, claimed_count, listed_skills, main  # noqa: E402

_REPO = Path(__file__).resolve().parents[1]


def _kit(root: Path, on_disk: list[str], rows: list[str], count: int | None = None) -> Path:
    skills = root / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    for name in on_disk:
        (skills / name).mkdir(parents=True, exist_ok=True)
        (skills / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
    for name in on_disk:
        # every skill carries the operator procedure beside its contract
        (skills / name / "SOP.md").write_text("# sop\n", encoding="utf-8")
    header = f"**{count} skills.**\n\n" if count is not None else ""
    table = "\n".join(f"| `{r}` | does | when | do not |" for r in rows)
    (skills / "map.md").write_text(
        f"# The skill map\n\n{header}| Skill | Does | Use when | Do NOT |\n"
        f"|---|---|---|---|\n{table}\n", encoding="utf-8")
    return root


def test_agreement_produces_nothing(tmp_path: Path) -> None:
    _kit(tmp_path, ["alpha", "beta"], ["alpha", "beta"], count=2)

    assert check(tmp_path) == []


def test_a_skill_on_disk_with_no_row_is_reported(tmp_path: Path) -> None:
    """The measured defect: five skills on disk and absent from the index, one of
    them a gate the pipeline cannot legally skip."""
    _kit(tmp_path, ["alpha", "plan-alignment"], ["alpha"], count=2)

    findings = check(tmp_path)

    assert any("missing_from_map" in f and "plan-alignment" in f for f in findings)


def test_a_row_for_a_deleted_skill_is_reported(tmp_path: Path) -> None:
    _kit(tmp_path, ["alpha"], ["alpha", "deleted-last-week"], count=1)

    findings = check(tmp_path)

    assert any("absent_from_disk" in f for f in findings)


def test_a_stale_count_is_reported(tmp_path: Path) -> None:
    """It said 35, there were 36. The count is the part a reader trusts without
    counting, which is exactly why it has to be checked."""
    _kit(tmp_path, ["alpha", "beta"], ["alpha", "beta"], count=36)

    assert any("count_disagrees" in f for f in check(tmp_path))


def test_no_count_claim_is_not_a_finding(tmp_path: Path) -> None:
    """A map that does not claim a number cannot be wrong about one."""
    _kit(tmp_path, ["alpha"], ["alpha"])

    assert check(tmp_path) == []


def test_a_row_naming_two_skills_covers_both(tmp_path: Path) -> None:
    """One line covers `backlog-init` and `backlog-review` where the two share a
    cross-reference. Counting only the first would report the second as missing."""
    skills = tmp_path / "skills"
    _kit(tmp_path, ["alpha", "beta"], ["alpha"], count=2)
    path = skills / "map.md"
    path.write_text(path.read_text(encoding="utf-8")
                    + "| `alpha`, `beta` | see above | — | — |\n", encoding="utf-8")

    assert check(tmp_path) == []


def test_a_missing_map_is_a_finding_not_a_pass(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir()

    assert any("missing_map" in f for f in check(tmp_path))


def test_names_are_read_from_the_first_cell_only(tmp_path: Path) -> None:
    """A prohibition mentioning another skill by name is prose, not a row."""
    _kit(tmp_path, ["alpha"], ["alpha"], count=1)
    path = tmp_path / "skills" / "map.md"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "| `alpha` | does | when | do not |",
        "| `alpha` | does | when | never call `beta` before this |"), encoding="utf-8")

    assert listed_skills(path) == {"alpha"}


def test_exit_code_is_one_on_a_disagreement(tmp_path: Path) -> None:
    _kit(tmp_path, ["alpha", "beta"], ["alpha"], count=2)

    assert main(["--root", str(tmp_path)]) == 1


def test_the_kit_itself_agrees() -> None:
    """The regression. It failed with five missing skills and a count of 36."""
    assert check(_REPO) == []
    assert claimed_count(_REPO / "skills" / "map.md") == len(
        list((_REPO / "skills").glob("*/SKILL.md")))


def test_a_skill_without_a_sop_is_reported(tmp_path: Path) -> None:
    """`SKILL.md` is the contract the agent executes; `SOP.md` is what a person
    needs to run the phase and act on what comes back. Measured 2026-08-31: only 6
    of 34 skills answered "it returned X, now what". A skill that ships without one
    is reachable and not operable."""
    _kit(tmp_path, ["alpha", "beta"], ["alpha", "beta"], count=2)
    (tmp_path / "skills" / "beta" / "SOP.md").unlink()

    findings = check(tmp_path)

    assert [f for f in findings if "missing_sop" in f and "beta" in f]
