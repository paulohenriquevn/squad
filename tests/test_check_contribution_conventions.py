"""The conventions, and the two an override cannot reach.

`CONTRIBUTING.md` instructed contributors to end commit messages with a co-authorship
trailer while zero of the last 200 commits carried one — measured 2026-09-11. The
document and the practice had disagreed long enough that nobody noticed, and an
open-source consumer reading the document would have followed it. That is why these are
computed rather than described.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "mechanisms" / "gates"))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
from check_contribution_conventions import (  # noqa: E402 — post-bootstrap import
    DEFAULT_SUBJECT_MAX,
    Conventions,
    check,
    check_message,
    load_conventions,
)

BODY = "\n\nthe measurement that made this necessary, stated so the next reader has it"


def _codes(message: str, conv: Conventions | None = None) -> set[str]:
    return {f.code for f in check_message("abc", message, conv or Conventions())}


# ------------------------------------------------------------------ the unoverridable


@pytest.mark.parametrize("trailer", [
    "Co-Authored-By: Someone <s@example.com>",
    "co-authored-by: someone",
    "CO-AUTHORED-BY: someone",
    "Co-authored_by: someone",
    "  Co-Authored-By: someone",
])
def test_a_coauthor_trailer_is_refused_in_any_spelling(trailer: str) -> None:
    """A template adds one without anyone deciding to, which is exactly why the match
    has to be loose."""
    assert "coauthor_trailer" in _codes(f"fix(x): a thing{BODY}\n\n{trailer}")


def test_an_override_that_would_allow_coauthorship_is_refused(tmp_path: Path) -> None:
    """Refused rather than ignored: a silently-dropped override reads as an accepted
    one, and the project would believe it had declared something it had not."""
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "contribution-overrides.txt").write_text("allow_coauthor = true\n",
                                                      encoding="utf-8")

    with pytest.raises(ValueError, match="cannot be overridden"):
        load_conventions(rules / "contribution-overrides.txt")


def test_an_unknown_override_key_is_refused(tmp_path: Path) -> None:
    """A typo that is ignored is a convention the project thinks it declared."""
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "contribution-overrides.txt").write_text("commit_type = fix,feat\n",
                                                      encoding="utf-8")

    with pytest.raises(ValueError, match="unknown key"):
        load_conventions(rules / "contribution-overrides.txt")


# ------------------------------------------------------------------ the shape


def test_a_well_formed_commit_passes() -> None:
    assert _codes(f"fix(gates): stop counting a wrap as a requirement{BODY}") == set()


def test_a_header_that_is_not_the_shape_is_reported() -> None:
    assert "header_shape" in _codes("fixed some stuff")


def test_an_undeclared_type_is_reported() -> None:
    assert "unknown_type" in _codes(f"wibble(x): a thing{BODY}")


def test_feat_and_fix_require_a_body() -> None:
    """The subject says WHAT changed; the body says what was true that made it
    necessary."""
    assert "body_missing" in _codes("feat(x): add a thing")
    assert "body_missing" in _codes("fix(x): repair a thing")
    assert "body_missing" not in _codes("docs: reword a paragraph")


def test_a_trailing_period_is_reported() -> None:
    assert "subject_trailing_period" in _codes(f"docs: a thing.{BODY}")


def test_a_merge_commit_header_is_not_the_authors_to_shape() -> None:
    """Git generates it. Failing a merge for its header punishes nobody's decision."""
    assert _codes("Merge pull request #76 from paulohenriquevn/workspace") == set()


def test_a_merge_commit_still_cannot_carry_a_trailer() -> None:
    assert "coauthor_trailer" in _codes(
        "Merge pull request #76\n\nCo-Authored-By: someone")


# ------------------------------------------------------------------ the limit


def test_the_subject_limit_is_derived_not_copied() -> None:
    """Measured over 300 subjects here: median 71, p90 85. A limit of 72 fails 44% of
    what this repository has always done, and a check that fails 44% of history is a
    preference nobody follows — it teaches people to ignore the checker. 85 fails 5%,
    which is the tail a limit is for.

    Same calibration `quality-init` performs from a project's real p90, applied to the
    kit's own default.
    """
    assert DEFAULT_SUBJECT_MAX == 85


def test_a_project_can_raise_the_limit(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "contribution-overrides.txt").write_text("subject_max = 120\n", encoding="utf-8")

    conv = load_conventions(rules / "contribution-overrides.txt")

    assert conv.subject_max == 120
    assert "override" in conv.source


def test_a_project_can_declare_its_own_types(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "contribution-overrides.txt").write_text("commit_types = fix,deps\n",
                                                      encoding="utf-8")

    conv = load_conventions(rules / "contribution-overrides.txt")

    assert conv.types == ("fix", "deps")
    assert "unknown_type" in _codes(f"feat(x): a thing{BODY}", conv)


# ------------------------------------------------------------------ honesty


def test_an_unresolvable_range_is_not_a_clean_range(tmp_path: Path) -> None:
    """A range that does not resolve is not a range where every commit is clean."""
    report = check(tmp_path, "nosuchref..HEAD")

    assert report.unmeasured_because
    assert report.findings == []


def test_this_repository_follows_its_own_conventions() -> None:
    """DOGFOODING, and it is the only test here whose subject is not the checker.

    Its outcome depends on the checkout's git history rather than on the code under
    test: somebody with a malformed commit among their last forty fails a test about
    `check_contribution_conventions`, and the failure names the wrong thing. The
    thirteen tests above pin the checker itself against fixtures and are what protects
    it; this one asks whether the kit obeys the rule it ships.

    Kept, because a kit failing its own gate is worth knowing — and the message says
    which of the two it is, so a reader is not sent to the checker over a commit.
    """
    report = check(_REPO, "-40")

    assert not report.unmeasured_because, report.unmeasured_because
    assert report.findings == [], (
        "this is a finding about THIS REPOSITORY'S last 40 commits, not about the "
        "checker — the checker's own behaviour is pinned by the fixtures above: "
        + str([f"{f.sha} {f.code}" for f in report.findings]))


def test_an_override_key_that_reaches_nothing_is_refused(tmp_path) -> None:
    """`branch_trunk` was accepted, parsed, validated as known — and applied to nothing.

    This checker's subject is COMMITS: header shape, subject length, body. It never read
    a branch name. `rules/contribution-overrides.txt` documented the key, so a project
    could set it, see it accepted, and believe it had declared something. An unknown key
    is refused here precisely so that cannot happen; the key was on the known list.
    """
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "contribution-overrides.txt").write_text("branch_trunk = main\n",
                                                      encoding="utf-8")

    with pytest.raises(ValueError, match="branch_trunk"):
        load_conventions(rules / "contribution-overrides.txt")


def test_the_rule_file_no_longer_documents_it() -> None:
    """A key refused by the code and offered by the docs is the same defect, mirrored."""
    rule = Path(__file__).resolve().parents[1] / "rules" / "contribution-overrides.txt"
    text = rule.read_text(encoding="utf-8")

    keys_section = text.split("# Keys:", 1)[1].split("# TWO THINGS", 1)[0]
    assert "branch_trunk    =" not in keys_section, (
        "the rule file still lists branch_trunk among the keys a project may set")


# ------------------------------------------------------- a scope may name two areas
#
# `fix(gates,boundary):` and `fix(board,gates):` were refused as `header_shape` — not
# for the scope's content but for the comma, which the header pattern had no room for.
# A change genuinely touching two areas then has three options: name one and be
# incomplete, invent a portmanteau nobody greps for, or drop the scope. All three lose
# the information the field exists to carry.
#
# Each segment is still validated on its own, so the rule that a scope is lowercase
# kebab-case is unchanged — what changed is that there may be more than one of them.


@pytest.mark.parametrize("header", [
    "fix(gates,boundary): a report from another run",
    "fix(board,gates): the board showed no work",
    "feat(a,b,c): three areas, one change",
])
def test_a_compound_scope_is_a_scope(header: str) -> None:
    assert _codes(header + BODY) == set()


@pytest.mark.parametrize("header", [
    "fix(gates, boundary): a space is not a separator",
    "fix(gates,): a trailing comma names no second area",
    "fix(,gates): nor does a leading one",
    "fix(Gates,boundary): segments are still lowercase",
])
def test_a_compound_scope_does_not_loosen_the_segment_rule(header: str) -> None:
    assert "header_shape" in _codes(header + BODY)


def test_a_declared_scope_list_is_checked_segment_by_segment() -> None:
    """`commit_scopes = gates, board` must accept `fix(gates,board):` and refuse a
    compound carrying one nobody declared — otherwise declaring scopes would silently
    stop applying the moment a commit named two."""
    conv = Conventions(scopes=("gates", "board"))

    assert _codes("fix(gates,board): both declared" + BODY, conv) == set()
    assert "unknown_scope" in _codes("fix(gates,ghost): one is not" + BODY, conv)


# ── a scope may name a PATH, not only a name ─────────────────────────────────
#
# The comma was added to this pattern because a change touching two areas had three bad
# options — name one and be incomplete, invent a portmanteau nobody greps for, or drop
# the scope — and all three lose what the field exists to carry. That argument was written
# into the file and applies unchanged to a slash.
#
# Measured 2026-09-23 on a consumer: five commits scoped `infra/tests`, refused as
# `header_shape` and reachable by NO override — `commit_scopes` is consulted only after
# HEADER_RE matches, so a project cannot declare its way out. Renaming it `infra-tests` is
# the portmanteau the comma fix already rejected: the scope names a directory and its
# tests, and the hyphen stops matching the path it names.

def test_a_scope_may_name_a_path() -> None:
    from check_contribution_conventions import HEADER_RE

    m = HEADER_RE.match("docs(infra/tests): state the fail-closed chart contract")

    assert m is not None, "a scope naming a directory and its tests is refused"
    assert m.group("scope") == "infra/tests"


def test_a_path_scope_composes_with_the_comma() -> None:
    """The two extensions are independent and a change may need both."""
    from check_contribution_conventions import HEADER_RE

    m = HEADER_RE.match("fix(infra/tests,gates): x")

    assert m is not None
    assert m.group("scope") == "infra/tests,gates"


def test_the_segment_rule_did_not_otherwise_loosen() -> None:
    """THE CONTROL. Each segment is still lowercase kebab-case; there may now be a slash
    BETWEEN segments, which is not the same as allowing anything."""
    from check_contribution_conventions import HEADER_RE

    for bad in ("docs(Infra/tests): x", "docs(infra/): x", "docs(/tests): x",
                "docs(infra//tests): x", "docs(infra tests): x"):
        assert HEADER_RE.match(bad) is None, f"{bad} should not parse"
