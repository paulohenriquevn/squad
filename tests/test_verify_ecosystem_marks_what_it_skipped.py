"""A check that could not look at its subject must not be drawn as a tick.

`verify_ecosystem` runs eighteen checks by delegating to gate scripts, and eight of
them return PASS when the script they delegate to is absent. Skipping is deliberate —
a consumer with a partial install must not fail over a gate it never installed — but
the mark printed for it was the same `✓` a real pass gets, with the reason on the
line below:

    ✓ Cross-references
      check_xrefs.py not installed — skipping

Measured on 2026-09-05 by hiding `mechanisms/gates/check_xrefs.py` and running the
verifier: that is the exact output. Nothing broken shipped — "Mechanisms inventory"
failed on the missing file and the run exited 1 — so this is about what the reader is
told, not about a hole in the gate. It is still the principle this repository states
elsewhere and enforces in `test_gates_say_what_they_examined.py`: a gate does not
report a result it did not observe.

The distinction has to survive in the RETURN VALUE and not only in the printed line,
because a caller reading `ok` cannot see prose.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module():
    path = ROOT / "mechanisms" / "gates" / "verify_ecosystem.py"
    spec = importlib.util.spec_from_file_location("_ve", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_ve"] = mod
    spec.loader.exec_module(mod)
    return mod


#: Each check that delegates, and the gate script it needs on disk.
DELEGATING = [
    ("check_xrefs", "check_xrefs.py"),
    ("check_skill_map", "check_skill_map.py"),
    ("check_readme_advisory_skills", "check_readme_advisory_skills.py"),
    ("check_squad_map", "check_squad_map.py"),
    ("check_mechanisms_inventory", "check_mechanisms_inventory.py"),
    ("check_phase_numbering", "check_phase_numbering.py"),
    ("check_wiki_migration", "check_wiki_migration.py"),
]


@pytest.mark.parametrize("func_name,script", DELEGATING)
def test_an_absent_gate_is_not_run_rather_than_passed(
    func_name: str, script: str, tmp_path: Path
) -> None:
    """An empty tree has none of these scripts, so every one takes its skip branch."""
    mod = _module()
    func = getattr(mod, func_name)
    ok, issues = func(tmp_path)
    assert ok is mod.NOT_RUN, (
        f"{func_name} returned {ok!r} for an absent {script}. A caller reading this "
        f"cannot tell a real pass from a check that never looked."
    )
    assert any("skipping" in note for note in issues), (
        "the reason has to travel with the verdict, not only with the mark"
    )


def test_not_run_is_not_a_failure() -> None:
    """The skip exists so a partial consumer install does not fail. Keep that.

    `NOT_RUN` must stay truthy: every existing caller writes `if ok:` and a sentinel
    that flipped to falsy would turn every partial install red — trading a misleading
    tick for a broken one, which is worse.
    """
    mod = _module()
    assert bool(mod.NOT_RUN) is True
    assert mod.NOT_RUN is not True, "it has to be distinguishable from a real pass"


def test_a_real_pass_is_still_plain_true() -> None:
    """The sentinel must not leak into checks that actually ran."""
    mod = _module()
    ok, _ = mod.check_python_syntax(ROOT)
    assert ok is True, "a check that examined its subject returns True, not the sentinel"


def test_the_runner_draws_a_different_mark_for_what_it_did_not_run(
    tmp_path: Path,
) -> None:
    """The mark is what a reader scans; it is the half that has to change.

    Invoked the way the gate actually runs — as a subprocess — against an empty
    directory, where every delegating check takes its skip branch. Asserting on the
    printed output rather than on an internal, because the printed output IS the
    deliverable here.
    """
    import subprocess

    script = ROOT / "mechanisms" / "gates" / "verify_ecosystem.py"
    result = subprocess.run(
        [sys.executable, str(script), "--ecosystem-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=180,
     check=False)
    out = result.stdout
    lines = out.splitlines()
    skips = [i for i, ln in enumerate(lines) if "not installed" in ln]
    assert skips, f"the empty tree should have produced skips. Output:\n{out}"
    for i in skips:
        mark = lines[i - 1]
        assert not mark.startswith("✓"), (
            f"{mark!r} is drawn as a pass, and the line under it says the gate was "
            f"never installed. A reader scanning marks is told this was checked."
        )
    assert "not run" in out.lower(), "the summary has to count what it could not check"
    # The EXIT CODE and the aggregate verdict, which this test ran past. An empty tree
    # is where every delegating check takes its skip branch, and that is exactly the
    # state where `ALL CHECKS PASSED` + exit 0 would be the whole defect this file is
    # about: nothing was checked, and the two things a script's caller reads said it
    # all passed. Asserting the marks and not the verdict left the worst outcome
    # unguarded.
    assert result.returncode != 0, (
        f"a run that checked nothing exited 0:\n{out[-800:]}")
    assert "ALL CHECKS PASSED" not in out, (
        "the aggregate claims a pass over a tree where every gate was skipped")


def test_the_verifier_examines_the_tree_it_was_pointed_at(tmp_path: Path) -> None:
    """`--ecosystem-dir` was accepted and read by nothing until 2026-09-05.

    `main()` took no arguments, so the flag fell on the floor and the verifier ran
    against whatever `_find_ecosystem_dir()` located — printing a full green report
    headed with THAT tree's path. Found by pointing it at an empty directory to test
    the skip marks above and getting sixteen ticks for the kit itself.

    The header is asserted because it is the only place the subject is named, and a
    report whose header names one tree and whose findings come from another is the
    worst of the failure modes this file is about.
    """
    import subprocess

    script = ROOT / "mechanisms" / "gates" / "verify_ecosystem.py"
    result = subprocess.run(
        [sys.executable, str(script), "--ecosystem-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=180, cwd=str(ROOT),
     check=False)
    assert str(tmp_path) in result.stdout, (
        f"pointed at {tmp_path} and reported on something else:\n{result.stdout[:400]}"
    )
    assert str(ROOT) not in result.stdout.splitlines()[0], (
        "the header names the kit, not the directory the caller asked about"
    )


def test_an_argument_it_does_not_understand_is_an_error(tmp_path: Path) -> None:
    """Silently ignoring a flag is how the one above went unnoticed for so long."""
    import subprocess

    script = ROOT / "mechanisms" / "gates" / "verify_ecosystem.py"
    result = subprocess.run(
        [sys.executable, str(script), "--not-a-real-flag"],
        capture_output=True, text=True, timeout=180, cwd=str(ROOT),
     check=False)
    assert result.returncode == 2, (
        f"exited {result.returncode}; an unrecognised argument must not be swallowed"
    )
    assert "unrecognised" in result.stderr.lower()


def test_a_run_where_nothing_ran_is_not_a_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The aggregate verdict is the half a CALLER reads, and it said the opposite.

    `all_pass` starts True and is cleared only in the `else` branch. `NOT_RUN` is
    truthy on purpose — a falsy sentinel would turn every partial install red — so a
    run where EVERY check took its skip branch fell through to `if all_pass:` and
    printed `=== ALL CHECKS PASSED ===`, returning 0.

    An empty directory does NOT reproduce it: the checks that read the tree directly
    (`Python syntax`, `Mechanisms inventory`) fail there and clear the flag, which is
    why the sibling test above passes today. The condition is every DELEGATING check
    skipping at once — a consumer who installed the kit without `mechanisms/gates/`.
    So this forces the state rather than hoping for it: every check is replaced with
    one that returns `NOT_RUN`, which is exactly what the shipped ones return when
    their script is absent.

    The per-check mark was already correct (`⊘`, covered above); this is about the
    line a script greps and the code a pipeline branches on.
    """
    mod = _module()
    names = [n for n in dir(mod) if n.startswith("check_")]
    assert len(names) > 10, f"expected the check_* family, found {names}"
    not_run = mod.NOT_RUN
    for name in names:
        # `*_a`: one entry in the checks list is a closure taking two arguments, and a
        # one-argument fake raised there instead of skipping — which cleared `all_pass`
        # and made this test pass for the wrong reason while the defect was live.
        setattr(mod, name, lambda *_a, **_k: (not_run, ["  forced: gate not installed"]))

    code = mod.main(["--ecosystem-dir", str(tmp_path)])
    out = capsys.readouterr().out

    assert "ALL CHECKS PASSED" not in out, (
        "every check was skipped and the run still reported a full pass:\n" + out
    )
    assert code != 0, (
        f"returned {code} when no gate ran. A caller cannot tell this from a real pass.\n{out}"
    )


def test_cross_references_are_checked_strictly(tmp_path: Path) -> None:
    """`--strict` is not cosmetic, and the installer already knew that.

    Without it `check_xrefs.py` prints its WARN findings and exits 0, so every WARN
    class reached this verifier as a pass. `mechanisms/distribution/install.sh` invokes the same
    script WITH `--strict`, and `.github/workflows/ci.yml` does too — so the smoke
    test was weaker than both callers that depend on it, and the same commit could
    be green here and refused at install time.
    """
    source = (ROOT / "mechanisms" / "gates" / "verify_ecosystem.py").read_text(encoding="utf-8")
    start = source.index("def check_xrefs(")
    body = source[start:source.index("\ndef ", start + 1)]
    assert "--strict" in body, (
        "check_xrefs is spawned without --strict, so a WARN reaches this gate as exit 0"
    )


def test_every_cycle_rule_on_disk_is_graded_not_six_from_a_list(tmp_path) -> None:
    """The tuple named six while fourteen were on disk, and the schema said every one.

    `cycle-design.md` was one of the eight nobody graded: it carried
    `## Why this cycle exists` instead of `## Purpose` and had no `## Anti-patterns`.
    That is what an ungraded rule drifts into, and the drift was invisible because the
    gate reported PASS over a list that did not contain it.
    """
    import verify_ecosystem as ve

    rules = tmp_path / "rules"
    rules.mkdir()
    good = "## Purpose\nx\n## Chain\nx\n## Anti-patterns\nx\n"
    (rules / "cycle-discover.md").write_text(good, encoding="utf-8")
    # A cycle the old tuple never named.
    (rules / "cycle-design.md").write_text("## Why this cycle exists\nx\n## Chain\nx\n",
                                           encoding="utf-8")
    (rules / "cycle-rule-schema.md").write_text("## Purpose\nx\n", encoding="utf-8")

    ok, issues = ve.check_cycle_rules(tmp_path)

    assert ok is False
    joined = "\n".join(issues)
    assert "cycle-design.md" in joined, f"the ungraded cycle was still not graded: {joined}"
    assert "cycle-rule-schema.md" not in joined, "the schema was graded as if it were a cycle"


def test_a_rules_tree_with_no_cycle_is_not_a_pass(tmp_path) -> None:
    import verify_ecosystem as ve

    (tmp_path / "rules").mkdir()

    ok, issues = ve.check_cycle_rules(tmp_path)

    assert ok is ve.NOT_RUN
    assert "nothing was graded" in "\n".join(issues)


def test_a_not_applicable_check_is_marked_not_run_rather_than_passed(tmp_path) -> None:
    """The module's own contract: "the skip stops being spelled True, because True is
    what a pass looks like".

    `check_chain_preconditions` returned True on both not-applicable paths while the line
    printed beside the tick said "not applicable". Three outputs — the mark, the tally and
    the sentence — and two of them said the check had passed.
    """
    import verify_ecosystem as ve

    # No BACKLOG.md: no chain runs here, so the question does not apply.
    ok, lines = ve.check_chain_preconditions(tmp_path)

    assert ok is ve.NOT_RUN, "a not-applicable check reported as a pass"
    assert any("not applicable" in ln for ln in lines)


def test_the_not_run_footer_does_not_name_one_cause_for_two(capsys) -> None:
    """A gate script that is not installed and a gate whose subject does not exist both
    land in the NOT_RUN tally. The footer named only the first, so a reader saw
    "the gate script was not installed" beside a gate that is installed and ran."""
    import inspect

    import verify_ecosystem as ve

    # `_sweep`, not `main`: the sweep was split out so `--json` could capture the
    # human text instead of racing it to stdout, and the footer went with the loop
    # that counts the skips. Reading `main` here passed vacuously for one commit —
    # the string was absent and the assertion was `not in`, so the check that the
    # footer names both causes had nothing left to read.
    footer = inspect.getsource(ve._sweep)

    assert "the gate script was not installed)" not in footer, (
        "the footer still asserts a single cause for every ⊘")
    assert "each ⊘ above says why" in footer


def _ve():
    """The module itself, imported from the gates directory it lives in."""
    import importlib
    import sys as _sys

    gates = str(ROOT / "mechanisms" / "gates")
    if gates not in _sys.path:
        _sys.path.insert(0, gates)
    return importlib.import_module("verify_ecosystem")


def test_the_json_gate_ritual_is_written_once() -> None:
    """Eight wrappers spelled out the same five steps, and the copies had drifted.

    Build the path under `mechanisms/gates/`, check it exists, run it with `--json`,
    `json.loads` the stdout, turn a decode error into a message. Two of the eight returned
    NOT_RUN for unparseable output where the other six returned False — the same failure
    drew a skip in one row and a cross in another, and no test could see the difference
    because each copy was correct on its own terms.
    """
    source = (ROOT / "mechanisms" / "gates" / "verify_ecosystem.py").read_text(encoding="utf-8")

    assert source.count("produced no usable JSON") == 1, (
        "the decode-failure message is spelled in more than one place again")
    assert source.count('_gate_payload(ecosystem_dir') >= 8, (
        "some JSON wrapper stopped going through the shared helper")


def test_an_unparseable_gate_is_a_failure_not_a_skip(tmp_path) -> None:
    """NOT_RUN is for the not-installed branch. A gate that RAN and produced unreadable
    output is a gate that failed, and the two must not share a mark."""
    gates = tmp_path / "mechanisms" / "gates"
    gates.mkdir(parents=True)
    (gates / "check_skill_map.py").write_text("print('not json at all')\n", encoding="utf-8")

    payload, refusal = _ve()._gate_payload(tmp_path, "check_skill_map", "--root", str(tmp_path))

    assert payload is None
    verdict, lines = refusal
    assert verdict is False, f"unparseable output marked {verdict!r}"
    assert any("no usable JSON" in ln for ln in lines)


def test_a_gate_that_is_not_installed_is_still_a_skip(tmp_path) -> None:
    payload, refusal = _ve()._gate_payload(tmp_path, "check_skill_map", "--root", str(tmp_path))

    assert payload is None
    verdict, _lines = refusal
    assert verdict is _ve().NOT_RUN
