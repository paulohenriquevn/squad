"""The one act reserved for a person, and the four ways this tool must not help too much.

`alignment_judge.py` can sign a brief and appends a note saying a judge signature is
worth less than a human one. `score_product_alignment.py` states its own limit: *"It
can compute the 90%; it cannot supply the signature, and there is no flag that makes
it."* Both are right, and the consequence was that the only act reserved for a person
had no mechanism at all.

The tests that matter here are the refusals. A tool that makes signing frictionless
turns a signature into a stamp, which is the failure the machine's refusal exists to
prevent.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from sign_document import (  # noqa: E402
    HUMAN_PREFIX,
    _agents_dir,
    check,
    git_authors,
    is_author,
    load,
    main,
    sign,
    waiting,
)

BRIEF = """# Brief

## Reviewer sign-off

- [ ] The problem is the real one
- [ ] The criteria are traceable
"""


def _doc(tmp_path: Path, body: str = BRIEF, name: str = "brief.md") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


# ------------------------------------------------------------------ the marker


def test_the_marker_lands_at_the_end_of_the_line(tmp_path: Path) -> None:
    """It landed INSIDE the sentence — `- [x] T  <!-- signed-by: … -->he problem is`.

    The regex captured one character after `]` instead of the rest of the line, so
    every scorer would still have found the marker and every human would have read a
    corrupted checklist.
    """
    doc = load(_doc(tmp_path))

    out = sign(doc, "paulo", today=date(2026, 9, 10))

    assert "- [x] The problem is the real one  <!-- signed-by: human/paulo -->" in out
    assert "he problem" not in out.replace("The problem", "")


def test_only_the_first_box_carries_the_marker(tmp_path: Path) -> None:
    """Repeating it on every line makes one signature look like several."""
    out = sign(load(_doc(tmp_path)), "paulo", today=date(2026, 9, 10))

    assert out.count("signed-by: human/paulo") == 1
    assert out.count("- [x]") == 2


def test_the_signer_is_recorded_as_a_person(tmp_path: Path) -> None:
    """`score_alignment.signed_by_is_human` reads `human` / `human/<name>`. Writing any
    other spelling would record a person's signature as an agent's."""
    out = sign(load(_doc(tmp_path)), "paulo", today=date(2026, 9, 10))

    assert f"signed-by: {HUMAN_PREFIX}paulo" in out
    assert "judge/" not in out


def test_a_name_already_prefixed_is_not_prefixed_twice(tmp_path: Path) -> None:
    out = sign(load(_doc(tmp_path)), "human/paulo", today=date(2026, 9, 10))

    assert "human/human/" not in out


# ------------------------------------------------------------------ the refusals


def test_an_already_signed_document_is_refused(tmp_path: Path) -> None:
    """Re-signing hides who signed first."""
    signed = sign(load(_doc(tmp_path)), "maria", today=date(2026, 9, 10))
    path = _doc(tmp_path, signed, "signed.md")

    refusal = check(load(path), "paulo")

    assert refusal is not None
    assert refusal.code == "already_signed"


def test_the_author_signing_their_own_work_is_refused(tmp_path: Path) -> None:
    """The same rule keeps a judge off a brief it wrote and an author off their own
    review panel. A reviewer who is not the author is the whole content of the check."""
    doc = load(_doc(tmp_path))
    doc.authors = ["paulo henrique", "paulo@example.com"]

    refusal = check(doc, "paulo")

    assert refusal is not None
    assert refusal.code == "author_signing_own_work"


def test_a_document_with_no_signoff_section_is_not_signable(tmp_path: Path) -> None:
    """Not a refusal — the document is not at the stage where a signature applies."""
    assert load(_doc(tmp_path, "# Just a document\n\nNo section.\n", "plain.md")) is None


def test_a_section_with_no_unticked_box_and_no_signer_is_refused(tmp_path: Path) -> None:
    path = _doc(tmp_path, "# B\n\n## Sign-off\n\nNothing to tick here.\n", "empty.md")

    refusal = check(load(path), "paulo")

    assert refusal is not None
    assert refusal.code == "nothing_to_tick"


# ------------------------------------------------------------------ the override


def test_a_sole_author_can_sign_by_declaring_it(tmp_path: Path) -> None:
    """On a project with one author the refusal blocks every signature, which would
    make the tool useless exactly where it is needed. Measured on this kit: one author
    across its whole history."""
    doc = load(_doc(tmp_path))
    doc.authors = ["paulo henrique"]

    refusal = check(doc, "paulo", despite="solo project, I am the only reviewer available")

    assert refusal is None


def test_the_override_is_written_into_the_document(tmp_path: Path) -> None:
    """It does not SILENCE the check — it records it. The next reader has to see that
    the reviewer and the author were the same person; that is the whole value of a
    check that can be overridden."""
    out = sign(load(_doc(tmp_path)), "paulo", today=date(2026, 9, 10),
               despite="solo project, I am the only reviewer available")

    assert "also an author of this document" in out
    assert "solo project, I am the only reviewer available" in out
    assert "weaker than one from a reviewer who did not write" in out


def test_a_thin_override_reason_is_refused(tmp_path: Path) -> None:
    """A reason nobody can argue with is the same as no reason."""
    doc = load(_doc(tmp_path))
    doc.authors = ["paulo henrique"]

    refusal = check(doc, "paulo", despite="because")

    assert refusal is not None
    assert refusal.code == "thin_override_reason"


# ------------------------------------------------------------------ authorship


def test_authorship_is_read_from_git_not_declared(tmp_path: Path) -> None:
    """The one refusal that cannot be self-declared is read from the record."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], capture_output=True, check=False)
    path = _doc(tmp_path)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=False)
    subprocess.run(["git", "-c", "user.email=p@example.com", "-c", "user.name=Paulo",
                    "commit", "-qm", "write"], cwd=tmp_path, capture_output=True, check=False)

    authors = git_authors(path)

    assert any("paulo" in a for a in authors), authors


def test_an_untracked_file_has_no_authors_and_the_check_cannot_fire(tmp_path: Path) -> None:
    """Absence must not read as a clean bill — it reads as unknown, and the preview
    says `(git could not say)` rather than implying the check passed."""
    assert git_authors(_doc(tmp_path)) == []


@pytest.mark.parametrize("signer,authors,expected", [
    ("paulo", ["paulo henrique", "paulo@example.com"], True),
    ("human/paulo", ["paulo henrique"], True),
    ("paulo@example.com", ["paulo@example.com"], True),
    ("maria", ["paulo henrique"], False),
    ("paulo", [], False),
    ("", ["paulo"], False),
])
def test_authorship_matching_is_loose_on_purpose(signer, authors, expected) -> None:
    """`paulo`, `Paulo Henrique` and `paulo@example.com` are one person. A check that
    only matched exactly would be a check that never fires."""
    assert is_author(signer, authors) is expected


# ------------------------------------------------------------------ the preview


def test_the_default_run_writes_nothing(tmp_path: Path) -> None:
    """A tool that makes signing frictionless turns a signature into a stamp."""
    path = _doc(tmp_path)
    before = path.read_text(encoding="utf-8")

    code = main([str(path), "--as", "maria"])

    assert code == 0
    assert path.read_text(encoding="utf-8") == before


def test_the_preview_states_what_the_signature_does_not_assert(tmp_path: Path, capsys) -> None:
    main([str(_doc(tmp_path)), "--as", "maria"])

    out = capsys.readouterr().out

    assert "WHAT IT DOES NOT" in out
    assert "Nothing was written" in out


def test_there_is_no_flag_that_skips_the_preview() -> None:
    """`--confirm` is a second deliberate act. A `--yes` would remove the only thing
    this tool contributes over `sed`."""
    source = (_SCRIPTS / "sign_document.py").read_text(encoding="utf-8")

    assert '"--yes"' not in source
    assert '"--force"' not in source


# ------------------------------------------------------------------ listing


def test_listing_finds_only_what_is_still_unsigned(tmp_path: Path) -> None:
    records = tmp_path / ".squad" / "records" / "alignment"
    records.mkdir(parents=True)
    (records / "open.md").write_text(BRIEF, encoding="utf-8")
    (records / "done.md").write_text(
        sign(load(_doc(tmp_path)), "maria", today=date(2026, 9, 10)), encoding="utf-8")

    found = [p.name for p in waiting(tmp_path)]

    assert "open.md" in found
    assert "done.md" not in found


def test_an_empty_listing_says_what_it_means(tmp_path: Path, capsys) -> None:
    """"Nothing waiting" and "everything signed" are different facts."""
    main(["--list", "--project", str(tmp_path)])

    assert "not the same as everything being signed" in capsys.readouterr().out


def test_specialists_are_found_even_though_they_live_outside_the_write_root(tmp_path: Path) -> None:
    """`rules/write-exemptions.txt` classes `<eco>/agents/` as `platform`: Claude Code
    resolves a subagent by reading the directory, so the location IS the interface.

    A listing that only swept `.squad/` reported "nothing waiting" against a project
    with seven unsigned specialists on disk — the exact wrong answer, delivered in the
    reassuring form.
    """
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "pkg.md").write_text(BRIEF, encoding="utf-8")

    found = [p.name for p in waiting(tmp_path)]

    assert "pkg.md" in found


def test_a_standalone_layout_finds_its_agents_too(tmp_path: Path) -> None:
    (tmp_path / "agents").mkdir(parents=True)
    (tmp_path / "agents" / "pkg.md").write_text(BRIEF, encoding="utf-8")

    assert _agents_dir(tmp_path) == tmp_path / "agents"
    assert [p.name for p in waiting(tmp_path)] == ["pkg.md"]
