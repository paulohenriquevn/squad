"""Updating 42 consumers by hand is how one adopter was nearly regressed.

While updating that adopter, five files had diverged from the kit — and the
divergence was LOCAL improvement (the `ECO=` convention in 9 skills,
check_xrefs's `_is_test_file`, the project's specialist list). Copying over them
would have erased all three. It only did not because the comparison was done file
by file first.

With 42 consumers that care does not scale as manual discipline. This is the
classifier that makes it mechanical: `identical` / `new` / `update` (the target is
on the base version, copying is safe) / `local-change` (the target diverged — do
NOT touch, name it for a human decision).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mechanisms" / "distribution"))

import sync_consumers
from sync_consumers import Action, classify


def test_absent_target_is_new() -> None:
    assert classify(source="a\n", base="a\n", target=None) is Action.NEW


def test_target_equal_to_source_is_identical() -> None:
    assert classify(source="a\n", base="old\n", target="a\n") is Action.IDENTICAL


def test_target_on_the_base_version_is_a_safe_update() -> None:
    """The common case: the consumer is on the kit's previous version."""
    assert classify(source="new\n", base="old\n", target="old\n") is Action.UPDATE


def test_target_that_diverged_from_base_is_a_local_change() -> None:
    """The adopter's lesson: divergence is local improvement until proven otherwise."""
    assert classify(
        source="new from the kit\n", base="old\n", target="old + a local fix\n"
    ) is Action.LOCAL_CHANGE


def test_file_absent_from_the_base_but_present_in_both_is_compared_by_content() -> None:
    """A file new in the kit that the target already has (written there first) is not
    a blind update: if the content differs, it is a local change."""
    assert classify(source="from the kit\n", base=None, target="from the kit\n") is Action.IDENTICAL
    assert classify(source="from the kit\n", base=None, target="from the project\n") is Action.LOCAL_CHANGE


# ---------------------------------------------------------------------------
# Lag is not local modification. The first dry-run across 40 consumers marked 231
# files as LOCAL_CHANGE, `mechanisms/distribution/install.sh` in almost all of them — and it was
# not local improvement, it was an install made from an older version. Comparing
# against ONE base only answers well for whoever sits exactly on it.
# ---------------------------------------------------------------------------

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from sync_consumers import classify_with_history  # noqa: E402 — post-bootstrap import


def test_content_that_matches_any_historical_kit_version_is_stale(tmp_path: Path) -> None:
    """If the target's content is a version the kit once had, it is behind — not
    modified. Updating is safe."""
    action = classify_with_history(
        source="v3\n", base="v2\n", target="v1\n", historical={"v1\n", "v2\n", "v3\n"}
    )
    assert action is Action.STALE


def test_content_in_no_historical_version_is_a_real_local_change(tmp_path: Path) -> None:
    action = classify_with_history(
        source="v3\n", base="v2\n", target="v2 + a project patch\n",
        historical={"v1\n", "v2\n", "v3\n"},
    )
    assert action is Action.LOCAL_CHANGE


def test_the_base_version_is_still_a_plain_update() -> None:
    action = classify_with_history(
        source="v3\n", base="v2\n", target="v2\n", historical={"v1\n", "v2\n"}
    )
    assert action is Action.UPDATE


# ---------------------------------------------------------------------------
# The delta must be CLOSED. Synced files cite other rules from the
# kit; in a lagging consumer those rules may not exist, and the target's
# check_xrefs starts failing on a broken reference — measured: 13 of the 40
# consumers went red after the first application, citing
# `rules/records-location.md` and `rules/live-target.txt`.
# ---------------------------------------------------------------------------

from sync_consumers import missing_rule_dependencies  # noqa: E402 (post-bootstrap)


def test_rules_cited_by_the_delta_but_absent_in_the_target_are_listed(tmp_path: Path) -> None:
    kit = tmp_path / "kit"
    (kit / "rules").mkdir(parents=True)
    (kit / "skills" / "x").mkdir(parents=True)
    (kit / "rules" / "present.md").write_text("ok", encoding="utf-8")
    (kit / "rules" / "absent.md").write_text("ok", encoding="utf-8")
    (kit / "skills" / "x" / "SKILL.md").write_text(
        "leia `rules/present.md` e `rules/absent.md`\n", encoding="utf-8")

    eco = tmp_path / "target" / ".claude"
    (eco / "rules").mkdir(parents=True)
    (eco / "rules" / "present.md").write_text("ok", encoding="utf-8")

    missing = missing_rule_dependencies(kit, eco, ["skills/x/SKILL.md"])
    assert missing == ["rules/absent.md"]


def test_a_rule_the_target_already_has_is_never_reported(tmp_path: Path) -> None:
    """A project's own config lives in `rules/*.txt`; overwriting it destroys a local
    adjustment. Only what is MISSING enters."""
    kit = tmp_path / "kit"
    (kit / "rules").mkdir(parents=True)
    (kit / "skills" / "x").mkdir(parents=True)
    (kit / "rules" / "live-target.txt").write_text("from the kit", encoding="utf-8")
    (kit / "skills" / "x" / "SKILL.md").write_text("see `rules/live-target.txt`", encoding="utf-8")

    eco = tmp_path / "target" / ".claude"
    (eco / "rules").mkdir(parents=True)
    (eco / "rules" / "live-target.txt").write_text("THE PROJECT'S OWN CONFIG", encoding="utf-8")

    assert missing_rule_dependencies(kit, eco, ["skills/x/SKILL.md"]) == []


# ---------------------------------------------------------------------------
# Grill kit-domain-agents-install, decision 5: a domain agent belongs to the
# PROJECT. Neither direction makes sense — neither the kit pushing, nor harvesting.
# ---------------------------------------------------------------------------

def test_agents_are_not_in_the_sync_scope() -> None:
    """Without this, the kit pushes the origin ecosystem's eight specialists back on
    every sync, undoing the cleanup the consumer did."""
    from sync_consumers import delta_prefixes
    assert "agents/" not in delta_prefixes()
    assert "skills/" in delta_prefixes()


def test_the_syncer_pushes_exactly_the_trees_the_installer_copies() -> None:
    """Two lists of the kit's own trees, in two languages, kept by hand.

    They drifted on 2026-09-02: `scripts/` was renamed to `mechanisms/` and only
    the installer was updated. From that commit the syncer propagated nothing
    from that tree — the fleet lead, the pipeline scheduler, the protocol client
    — while printing a delta as though the delta were whole. Five fixes of that
    day, one of them closing a gate that let unsigned items into PLAN, would have
    reached no consumer by the supported path.

    Deriving one from the other at runtime would couple a Python module to a
    shell script's parse. Failing loudly when they disagree costs nothing and
    catches the rename, which is the only way they ever diverge.
    """
    install = (Path(__file__).resolve().parents[1]
               / "mechanisms" / "distribution" / "install.sh").read_text(encoding="utf-8")

    copied = re.search(r"^for item in ((?:[a-z_]+ )+[a-z_]+); do$", install, re.M)
    assert copied, "install.sh no longer has the loop that copies the kit's trees"
    installed = {f"{name}/" for name in copied.group(1).split()}

    assert set(sync_consumers.delta_prefixes()) == installed, (
        "the syncer and the installer disagree about which trees the kit owns; "
        "a tree the installer copies but the syncer skips receives no update, "
        "and the dry-run reports its absence as a complete delta")


def test_no_prefix_names_a_directory_that_is_not_there() -> None:
    """A dead prefix is how the drift stays invisible: it keeps the tuple looking
    populated while matching nothing."""
    kit = Path(__file__).resolve().parents[1]

    missing = [p for p in sync_consumers.delta_prefixes() if not (kit / p).is_dir()]

    assert not missing, f"prefix(es) matching no directory in the kit: {missing}"


def test_the_history_scan_is_paid_once_per_file(tmp_path) -> None:
    """`historical_versions` spawns `git rev-list --all` plus one `git show` per revision.

    It is called from inside the per-file loop of `sync_target`, which runs once per
    CONSUMER — so syncing one file into eight consumers replayed the same history eight
    times, and a file with forty revisions cost forty processes each pass. The answer
    depends on the kit's history and the path, neither of which changes within a run.
    """
    import sync_consumers

    assert hasattr(sync_consumers.historical_versions, "cache_info"), (
        "the history scan is not memoised")


def test_the_documented_composition_is_the_one_that_runs() -> None:
    """`classify_with_history` had no production caller.

    `sync_target` carried an inline copy of the same two steps, so the branch the tests
    exercised was not the branch that ran — and the two could drift without a single test
    going red. The function's own docstring calls it "`classify`, plus the question it
    did not ask".
    """
    import inspect

    import sync_consumers

    assert "classify_with_history(" in inspect.getsource(sync_consumers.sync_target), (
        "sync_target still carries its own copy of the composition")


def test_no_portuguese_survives_in_this_module() -> None:
    """`rules/english-only.md` makes the repository English-only, and this file's
    docstrings were the exception the gate's marker set could not see."""
    import re

    import sync_consumers

    source = Path(sync_consumers.__file__).read_text(encoding="utf-8")
    accented = re.findall(r"^.*[ãõçáéíóúâêô].*$", source, re.M)
    offenders = [ln.strip() for ln in accented
                 if not ln.lstrip().startswith("#") or "english-only:" not in ln]

    assert not [o for o in offenders if "Classifica" in o or "consumidor" in o], offenders[:5]  # english-only: the two spellings this test exists to refuse, quoted verbatim
