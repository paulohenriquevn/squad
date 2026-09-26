"""Running a criterion instead of reading it.

`score_alignment` grades a criterion `executable` from a text match over the bullet: it
asks whether a command is NAMED, never whether it could run or whether its answer
distinguishes anything. A consumer measured the consequence — a brief scored 14/14
executable where two criteria could not pass at all, and roughly thirty criteria across
eighteen briefs returned the same answer before and after the work.

None of that is visible to a reader of the text. All of it is visible in one run.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

# Imports below the bootstrap, not at the top: the kit ships as loose scripts, so
# `squad` and its sibling modules are importable only after sys.path is extended.
# That is what E402 cannot see here, and why each import below suppresses it.
import check_criteria_discriminate as cd  # noqa: E402 — post-bootstrap import


def _brief(tmp_path: Path, *bullets: str) -> Path:
    path = tmp_path / "b-001-alignment.md"
    path.write_text("# Brief\n\n## Acceptance Criteria\n\n"
                    + "".join(f"- {b}\n" for b in bullets), encoding="utf-8")
    return path


# ── the class this exists to catch ──────────────────────────────────────────

def test_a_criterion_that_already_passes_is_refused(tmp_path):
    """It cannot tell a finished item from an unstarted one, whatever it says."""
    brief = _brief(tmp_path, "AC-001: `echo 1` prints 1")
    rep = cd.run(brief, tmp_path)
    assert len(rep.already_passing) == 1


def test_a_criterion_that_fails_today_has_something_to_prove(tmp_path):
    brief = _brief(tmp_path, "AC-001: `echo 0` prints 1")
    rep = cd.run(brief, tmp_path)
    assert rep.already_passing == []


def test_an_exit_zero_criterion_that_already_exits_zero_is_refused(tmp_path):
    """`go test -run <pattern-that-matches-nothing>` exits 0 with `[no tests to run]`.

    Measured on a consumer: eight criteria in one brief were satisfied by writing no
    test at all.
    """
    brief = _brief(tmp_path, "AC-001: `true` exits 0")
    assert cd.run(brief, tmp_path).already_passing


# ── what it must not claim ──────────────────────────────────────────────────

def test_a_criterion_whose_expectation_is_unstated_is_undecidable_not_sound(tmp_path):
    """Reporting a criterion as sound because the comparison was too hard is the
    failure this file exists to end, one level up."""
    brief = _brief(tmp_path, "AC-001: `echo hello` behaves correctly")
    rep = cd.run(brief, tmp_path)
    assert rep.already_passing == []
    assert len(rep.undecidable) == 1


def test_a_placeholder_criterion_is_not_run_and_not_counted_as_sound(tmp_path):
    brief = _brief(tmp_path, "AC-001: `go test ./<module>/...` exits 0")
    rep = cd.run(brief, tmp_path)
    assert rep.unrunnable and not rep.already_passing
    assert "placeholder" in rep.results[0].note


def test_a_bullet_naming_no_command_is_reported_as_unrunnable(tmp_path):
    brief = _brief(tmp_path, "AC-001: the system feels faster")
    rep = cd.run(brief, tmp_path)
    assert rep.unrunnable
    assert "no runnable command" in rep.results[0].note


def test_a_hanging_criterion_is_stopped_and_named(tmp_path):
    # The subprocess is mocked rather than a slow command chosen: every command slow
    # enough to hang is either off the allowlist or arbitrary-code execution, so a real
    # one would test the allowlist instead of the timeout.
    import subprocess as _sp
    brief = _brief(tmp_path, "AC-001: `grep -c x f` prints 1")

    def _hang(*args, **kwargs):
        raise _sp.TimeoutExpired("grep", 1.0)

    monkeypatch_target = cd.subprocess.run
    cd.subprocess.run = _hang
    try:
        rep = cd.run(brief, tmp_path, timeout=1.0)
    finally:
        cd.subprocess.run = monkeypatch_target
    assert rep.unrunnable
    # The note lives on the CLAUSE since decomposition: a conjunction can have one
    # clause that hangs and another that answered, and a single note could not say so.
    assert "did not finish" in rep.results[0].clauses[0].note


# ── the honest limits, stated in the output ─────────────────────────────────

def test_the_report_says_it_checked_one_state_of_three(tmp_path):
    """A green run means "no criterion is vacuous in the cheapest way". It does not
    mean the criteria are good, and the page must not let a reader think it does."""
    brief = _brief(tmp_path, "AC-001: `echo 0` prints 1")
    text = cd.render(cd.run(brief, tmp_path), brief)
    assert "does not" in text and "wrong implementation" in text


def test_a_brief_with_no_acceptance_section_is_not_measured(tmp_path, monkeypatch):
    path = tmp_path / "empty.md"
    path.write_text("# Brief\n\nno criteria here\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv",
                        ["check_criteria_discriminate.py", str(path),
                         "--repo-root", str(tmp_path)])
    assert cd.main() == 2


def test_exit_zero_only_when_every_criterion_fails_today(tmp_path, monkeypatch):
    brief = _brief(tmp_path, "AC-001: `echo 0` prints 1", "AC-002: `false` exits 0")
    monkeypatch.setattr(sys, "argv",
                        ["check_criteria_discriminate.py", str(brief),
                         "--repo-root", str(tmp_path)])
    assert cd.main() == 0


# ── decomposition: N clauses need N readings ────────────────────────────────

def test_every_runnable_clause_is_executed(tmp_path):
    """Only the first span was run until decomposition, so the second half of a
    conjunction was never executed at all — not folded into one verdict, skipped."""
    brief = _brief(tmp_path, "AC-001: `echo a` prints a AND `echo b` prints b")
    rep = cd.run(brief, tmp_path)
    assert [c.command for c in rep.results[0].clauses] == ["echo a", "echo b"]


def test_a_vacuous_clause_masked_by_a_failing_one_is_caught(tmp_path):
    """The case that motivated the executor and that one verdict could not see.

    Measured on a consumer's B-067:

        clause 1 (the gate exists)  -> 0, because the gate is not written yet
        clause 2 (`go test -run TestGateRegistryParity`) -> exit 0, [no tests to run]

    The conjunction fails today, so a single reading calls the criterion sound. But
    clause 2 exits 0 today and will exit 0 after the work, because the test it names
    exists nowhere — so when the gate is built the whole criterion passes with clause 2
    measuring nothing.
    """
    brief = _brief(tmp_path, "AC-004: `false` prints 1 AND `true` exits 0")
    rep = cd.run(brief, tmp_path)
    result = rep.results[0]
    assert result.passes_today is False, "the conjunction must still read as failing"
    assert len(result.passing_clauses) == 1, "and the vacuous half must be named"
    assert rep.already_passing, "a criterion carrying one is refused"


def test_each_clause_is_judged_against_its_own_expectation(tmp_path):
    """`prints 1` and `exits 0` are different questions about different clauses.

    Applying the bullet's first expectation to every clause made one that exits 0 read
    as failing — the exact opposite of the finding decomposition exists to surface.
    """
    brief = _brief(tmp_path, "AC-001: `echo 1` prints 1 AND `false` exits 0")
    clauses = cd.run(brief, tmp_path).results[0].clauses
    assert clauses[0].passes_today is True
    assert clauses[1].passes_today is False


def test_the_refusal_separates_the_whole_from_the_half(tmp_path):
    """A reader needs to know which of the two shapes they have."""
    brief = _brief(tmp_path, "AC-001: `false` prints 1 AND `true` exits 0")
    text = cd.render(cd.run(brief, tmp_path), brief)
    assert "FAIL as a whole today" in text
    assert "will pass after the work too" in text


# ── a verification does not survive the tree it measured ────────────────────

def test_the_result_is_stamped_with_the_tree_it_read(tmp_path):
    """Not theoretical. On 2026-09-14 the kit wrote `go | api/go.mod | ENABLED` into a
    consumer's language config to unblock its quality gate, and a criterion of that
    consumer's B-034 — `grep -cE '^[[:space:]]*go[[:space:]]*\\|' <that file>` — went
    from discriminating to inert in the same minute. The criterion did not change.

    A reader comparing yesterday's run to today's decision needs to know they are not
    the same question.
    """
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=False)
    (tmp_path / "f").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=False)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=t@t",
                    "-c", "user.name=t", "commit", "-qm", "t"], check=False)
    brief = _brief(tmp_path, "AC-001: `echo 0` prints 1")
    rep = cd.run(brief, tmp_path)
    assert rep.head, "a versioned tree must be stamped"
    assert "read against" in cd.render(rep, brief)


def test_a_dirty_tree_is_named_because_its_answers_do_not_reproduce(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=False)
    (tmp_path / "f").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=False)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=t@t",
                    "-c", "user.name=t", "commit", "-qm", "t"], check=False)
    (tmp_path / "f").write_text("changed", encoding="utf-8")
    brief = _brief(tmp_path, "AC-001: `echo 0` prints 1")
    rep = cd.run(brief, tmp_path)
    assert rep.dirty
    assert "DIRTY" in cd.render(rep, brief)


def test_an_unversioned_tree_says_so_rather_than_claiming_a_sha(tmp_path):
    brief = _brief(tmp_path, "AC-001: `echo 0` prints 1")
    rep = cd.run(brief, tmp_path)
    assert rep.head == ""
    assert "unversioned tree" in cd.render(rep, brief)


def test_the_report_warns_that_the_reading_expires(tmp_path):
    """The sentence that would have saved the B-034 clause."""
    brief = _brief(tmp_path, "AC-001: `echo 0` prints 1")
    text = cd.render(cd.run(brief, tmp_path), brief)
    assert "does not survive the tree it measured" in text
    assert "about to implement on" in text


# ── a guard passing today is the criterion working ──────────────────────────

def test_a_declared_guard_is_not_counted_as_a_defect(tmp_path):
    """Reported by a consumer across 16 briefs, and the distinction is the point.

        B-029 AC-007  "the declared non-goal holds"                 -> guard
        B-020 AC-006  "the declared terminal sets are untouched"    -> guard
        B-012 AC-001  "the four divergences are gone"               -> DEFECT

    The first two passing today is the criterion working; the third passing today is an
    item that closes on work nobody did. A `test -s store.go` asserting a file still
    exists would be a BROKEN item if it failed today.
    """
    brief = _brief(tmp_path,
                   "AC-006: the declared terminal sets are untouched — `true` exits 0")
    rep = cd.run(brief, tmp_path)
    assert rep.guards, "a declared guard must be recognised"
    assert rep.already_passing == [], "and must not be counted as a defect"


def test_a_real_defect_is_still_refused_beside_a_guard(tmp_path):
    brief = _brief(tmp_path,
                   "AC-006: the terminal sets are untouched — `true` exits 0",
                   "AC-001: the four divergences are gone — `true` exits 0")
    rep = cd.run(brief, tmp_path)
    assert len(rep.guards) == 1
    assert len(rep.already_passing) == 1


def test_the_guard_label_is_read_narrowly(tmp_path):
    """Without a label a criterion counts as a defect, which is the safe direction.

    A defect called a guard is silence; a guard called a defect is a question.
    """
    brief = _brief(tmp_path, "AC-001: the endpoint returns quickly — `true` exits 0")
    assert cd.run(brief, tmp_path).guards == []


def test_the_report_names_guards_separately_from_defects(tmp_path):
    brief = _brief(tmp_path, "AC-006: nothing stops compiling — `true` exits 0")
    text = cd.render(cd.run(brief, tmp_path), brief)
    assert "pass BY DESIGN" in text
    assert "passes by design (guard)" in text or "guard, by design" in text


# ── the parser must not invent clauses ──────────────────────────────────────

def test_a_tool_named_in_prose_is_not_run_as_a_clause(tmp_path):
    """Measured on a consumer's B-012: `awk` and `diff` sit in backticks inside the
    prose around the command, match the runnable vocabulary, and were executed — `awk`
    alone exits 0 and was reported as a clause that already passes, inflating the count
    of inert clauses with artefacts of this parser."""
    brief = _brief(tmp_path, "AC-003: `echo 1` prints 1, using `awk` and `diff`")
    clauses = cd.run(brief, tmp_path).results[0].clauses
    assert [c.command for c in clauses] == ["echo 1"]


def test_a_self_sufficient_command_still_counts_with_one_token(tmp_path):
    brief = _brief(tmp_path, "AC-001: `true` exits 0")
    assert cd.run(brief, tmp_path).results[0].clauses


# ── this executes commands out of a document ────────────────────────────────

def test_a_clause_that_moves_work_is_refused_before_it_runs(tmp_path):
    """Measured on a consumer on 2026-09-15, before this existed.

    A criterion carried `git stash push` in its backticks, this executor ran it, and it
    pushed SEVEN entries onto a stash stack shared by six worktrees — one of them
    carrying twenty uncommitted CHANGELOG lines, which left the tree.

    This file's own docstring already said "running commands out of a document is the
    risk it is". Saying it is not protecting against it.
    """
    for dangerous in ("git stash push -m x", "git reset --hard HEAD",
                      "git checkout main", "git worktree remove /tmp/x",
                      "rm -rf build", "curl -X POST https://api/deploy",
                      "sudo systemctl stop x"):
        assert cd._refused_command(dangerous), dangerous


def test_a_dangerous_command_hidden_inside_bash_c_is_still_refused():
    """`bash -c '<script>'` hides its real commands inside the quotes, and a split that
    does not enter them lets exactly the measured case through."""
    assert cd._refused_command("bash -c 'git stash && test 1 -eq 1'")
    assert cd._refused_command('bash -c "rm -rf x"')


def test_the_reading_commands_a_criterion_needs_still_run():
    """An allowlist that refuses the legitimate case is a tool nobody uses."""
    for safe in ("grep -c foo src/", "go test ./... -run X", "git log --oneline -1",
                 "git diff HEAD", "bash -c 'test $(ls | wc -l) -eq 3'", "echo 1"):
        assert not cd._refused_command(safe), safe


def test_a_refused_clause_is_unverified_and_never_sound(tmp_path):
    """The honest answer. "Ran something unknown against your tree" is not."""
    brief = _brief(tmp_path, "AC-001: `git stash push` exits 0")
    rep = cd.run(brief, tmp_path)
    assert rep.refused
    assert rep.already_passing == []
    assert rep.results[0].clauses[0].passes_today is None


def test_a_built_binary_is_refused_and_the_reason_says_run_it_yourself(tmp_path):
    """The common legitimate case, refused deliberately.

    `/tmp/project-cli quality --list` appears throughout a real registry. That binary can
    do anything, and "not verified" is an honest answer while "ran something unknown
    against your tree" is not — so the reader is told precisely that, and can run it.
    """
    assert "run it" in cd._refused_command("/tmp/project-cli quality --list")


# ── the allowlist refused commands nobody could have run any other way ──────


def test_a_subshell_scoping_a_command_to_a_module_is_readable():
    """`(cd api && go test ./...)` is how a workspace repository says "in this module",
    and there is no other way to say it.

    Two faults met here. `cd` was not on the allowlist though it is a pure builtin that
    changes this shell's directory and touches nothing else; and the tokenizer split on
    `)` but not `(`, so the opening paren stayed glued to the word after it and the
    command was refused as the unknown `(cd`. A parsing miss reported as a policy
    decision is the worst way to be wrong — the reader is told the command is forbidden
    when it was never read.

    Measured on a consumer 2026-09-15: 6 of one item's 12 clauses, on the item chosen
    BECAUSE the chain had never been its obstacle.
    """
    assert cd._refused_command("(cd api && go test ./...)") == ""
    assert cd._refused_command("cd api && grep -c 'x' f.go") == ""


def test_the_subshell_fix_did_not_stop_the_allowlist_reading_inside_it():
    """Splitting on `(` means what is inside the subshell is now READ. Before, it was
    refused for the wrong reason — which happened to be safe, and would have stopped
    being safe the moment `cd` was allowed without the split."""
    assert cd._refused_command("(cd api && rm -rf build)") != ""
    assert cd._refused_command("(cd api && git reset --hard)") != ""
    assert cd._refused_command("(cd api && git checkout main)") != ""


def test_a_wrapper_does_not_launder_the_command_it_runs():
    """`env` was already on the allowlist, and a wrapper allowed without reading its
    payload is how `timeout 60 rm -rf /` walks through. Each wrapper is transparent to
    whatever it runs, so the payload is re-checked as its own command."""
    assert cd._refused_command("timeout 60 go test ./...") == ""
    assert cd._refused_command("env GOFLAGS=-mod=mod go build ./...") == ""
    assert cd._refused_command("timeout 60 rm -rf /") != ""
    assert cd._refused_command("env FOO=1 git stash") != ""
    assert cd._refused_command("xargs rm") != ""
    assert cd._refused_command("timeout 5 sudo reboot") != ""


def test_git_hash_object_writes_nothing_without_the_flag_that_writes():
    """`git hash-object` computes a hash; `-w` is what stores the object. The blanket
    refusal charged the safe form for the dangerous one, and pinning a file by its hash
    is a common and entirely read-only shape."""
    assert cd._refused_command("git hash-object api/go.mod") == ""
    assert cd._refused_command("git hash-object -w api/go.mod") != ""


def test_an_operand_is_not_refused_as_an_unknown_command():
    """After splitting on `$(`, `)` and `&&`, the leftovers are operands — `1` from
    `-eq 1`, `ctx,` from inside a grep pattern. Refusing them announced a policy
    decision about something that was never a command; on a consumer that was the
    entire remaining refusal set for one item.

    Safe in the direction that matters: bash would not run these either, and every real
    command on the line is still checked.
    """
    assert cd._refused_command("test $(grep -c 'x' f.go) -eq 1") == ""
    assert cd._refused_command("grep -c 'ctx, err' f.go") == ""
    # The real command on a line full of operands is still read.
    assert cd._refused_command("test $(ls) -eq 1 && sudo reboot") != ""
    assert cd._refused_command("echo hi; git checkout main") != ""


def test_mktemp_builds_the_control_that_makes_a_criterion_discriminate():
    """It creates a scratch path under the system temp directory and touches nothing
    else; refusing it cost 7 clauses on one consumer item, all of them building the
    negative control the criterion needs to mean anything."""
    assert cd._refused_command("mktemp -d") == ""
    assert cd._refused_command("(cd api && go test ./...) ; exit 0") == ""


def test_a_binary_the_criterion_built_is_still_refused():
    """The deliberate trade, unchanged: that binary can do anything, and "not verified"
    is an honest answer while "ran something unknown against your tree" is not."""
    assert cd._refused_command("/tmp/project-cli quality --list") != ""


def test_a_runner_that_says_it_executed_nothing_has_not_answered() -> None:
    """The class a consumer session named as the one nobody counts: "the honest statement
    about today is not 24 defects found; it is 24 found and an unknown number that
    returned exit 0."

    Its four examples were a `grep` honouring `.gitignore`, a `cd` failing into the
    original directory, a `\\s` crossing a newline, and a `find -newermt` window returning
    zero over a file inside it. Every one was found by accident while looking for
    something else.

    `None` rather than `False`: the criterion may be sound against a tree where the test
    exists. What is unknown is today's answer, and "could not decide" is the honest word.
    """
    class _Result:
        def __init__(self, code, out, err=""):
            self.exit_code, self.stdout, self.stderr = code, out, err

    assert cd._decide(_Result(0, "no tests to run\n"), "exit:0")[0] is None
    assert cd._decide(_Result(0, "collected 0 items\n"), "exit:0")[0] is None
    assert cd._decide(_Result(0, "no tests ran\n"), "print:3")[0] is None


def test_a_silent_command_is_not_a_command_that_measured_nothing() -> None:
    """The distinction this rests on. `test -f x` and `git diff --quiet` answer by
    exiting and say nothing at all, and reading silence as vacuity would refuse the
    clearest criteria in the corpus. Only a runner's own STATEMENT that it ran nothing
    counts.
    """
    class _Result:
        def __init__(self, code, out, err=""):
            self.exit_code, self.stdout, self.stderr = code, out, err

    assert cd._decide(_Result(0, ""), "exit:0")[0] is True
    assert cd._decide(_Result(0, "ok  pkg  0.2s\n"), "exit:0")[0] is True
    assert cd._decide(_Result(1, "--- FAIL\n"), "exit:0")[0] is False


def test_the_guard_finds_nothing_in_the_current_corpus_and_that_is_reported() -> None:
    """Measured on a consumer 2026-09-15: 185 executed clauses across 12 briefs, zero
    caught. The guard discriminates in both directions above and finds nothing today.

    That is worth writing down rather than leaving implied: a guard that has never fired
    is evidence about the corpus, not about the guard, and the two are easy to confuse
    when someone reads the fix later and wonders what it bought.
    """
    assert cd._MEASURED_NOTHING_RE.search("no tests to run")
    assert not cd._MEASURED_NOTHING_RE.search("ok  github.com/example/pkg  0.2s")


class _Ran:
    def __init__(self, code, out, err=""):
        self.exit_code, self.stdout, self.stderr = code, out, err


def test_a_criterion_that_states_a_bound_is_compared_as_one() -> None:
    r"""`prints 4 or more` was compared for EQUALITY, so a correct `6` read as a failure.

    Worse than the false verdict is its direction: the check reported "discriminates"
    because the number DIFFERED, not because the criterion was unmet. A discrimination
    check satisfied by difference measures nothing about the criterion.

    Probed at a consumer session's request after it found one case, and wider than the
    case that prompted it: every comparative form in the vocabulary was mis-read — `at
    least 4` extracted the word `at`, `>= 3` extracted `>=`.

    Measured through `_bound_of` itself: 16 clauses across 11 of that registry's briefs
    state a bound. It took four numbers to get there — 14 and 19 from two ad-hoc sweep
    regexes, one per session; then 15 from the RIGHT function with its input pre-filtered
    to lines matching `^\s*-\s*AC-`; then 16, the function handed every line.

    The last step is the transferable one: **calling the deciding function is not enough
    if you choose what to feed it.** A pre-filter is a second, undeclared predicate, and
    it fails silently in the direction of fewer results — which reads as clean. The brief
    it dropped had its bounded clause on a continuation line, invisible to any sweep
    assuming one criterion per bullet.
    """
    assert cd._decide(_Ran(0, "6\n"), "print:>=4")[0] is True
    assert cd._decide(_Ran(0, "3\n"), "print:>=4")[0] is False
    assert cd._decide(_Ran(0, "2\n"), "print:<=2")[0] is True


def test_an_exact_expectation_stays_exact() -> None:
    """Widening the comparison must not loosen the criteria that name a value."""
    assert cd._decide(_Ran(0, "4\n"), "print:4")[0] is True
    assert cd._decide(_Ran(0, "6\n"), "print:4")[0] is False


def test_output_that_is_not_a_number_cannot_be_compared_to_a_bound() -> None:
    """None, not False. The criterion may be sound; what failed is the comparison."""
    decided, note = cd._decide(_Ran(0, "ok\n"), "print:>=4")
    assert decided is None
    assert "not a number to compare" in note


def test_every_comparative_form_in_the_vocabulary_is_recognised() -> None:
    for text, expected in (
        ("`grep -c 'x' f.go` prints 4 or more", (">=", 4)),
        ("prints `4` or more", (">=", 4)),
        ("prints at least 4", (">=", 4)),
        ("prints >= 3", (">=", 3)),
        ("prints at most 2", ("<=", 2)),
        ("prints 3 or fewer", ("<=", 3)),
        ("prints no fewer than 5", (">=", 5)),
        ("prints 4", None),
        ("exits 0", None),
    ):
        assert cd._bound_of(text) == expected, text


def test_a_writing_flag_is_a_whole_token_not_a_substring():
    """`-i` was matched anywhere two characters appeared, so `-invocation` in a kebab-case
    test file and `--ignore-scripts` were refused as `sed -i`. Found on a real brief whose
    criterion named `a-limit-survives-a-cold-invocation.test.ts`."""
    for reads in ("npx vitest run tests/a-cold-invocation.test.ts",
                  "npm ci --ignore-scripts",
                  "git log --output-indicator-new=x -1",
                  "grep -c -- '--force' README.md"):
        assert cd._refused_command(reads) == "", (reads, cd._refused_command(reads))


def test_a_short_flag_is_read_against_the_command_it_belongs_to():
    """`-o` writes for `sort` and extracts for `grep`; `-d` deletes for `git branch` and
    lists directories for `ls`. A flag means what its command says it means."""
    for reads in ("grep -o foo f.txt", "ls -d src", "mktemp -d", "git diff -D HEAD"):
        assert cd._refused_command(reads) == "", (reads, cd._refused_command(reads))


def test_the_writing_flags_are_still_refused_after_tokenising():
    """The control: reading flags as tokens must not loosen the guard it replaces."""
    for writes in ("sed -i s/a/b/ f.txt", "sed -ni p f.txt", "sed -i.bak s/a/b/ f.txt",
                   "sed 's/a/b/' -i f.txt", "sed --in-place s/a/b/ f.txt",
                   "bash -c 'sed -i s/a/b/ f.txt'", "xargs sed -i s/a/b/",
                   "yq -i '.a = 1' f.yaml", "awk -i inplace '{print}' f.txt",
                   "sort -o out.txt in.txt", "git log --output=out.txt",
                   "git branch -d feature", "git branch -D feature",
                   "git tag --delete v1", "git branch --force main HEAD~1",
                   "sed \"-i\" s/a/b/ f.txt"):
        assert cd._refused_command(writes), writes
