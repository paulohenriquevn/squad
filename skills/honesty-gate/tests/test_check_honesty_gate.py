"""The gate on the claim, which for most of its life was honoured by memory.

Every other gate in this kit asks whether the WORK is done. This one asks whether
the CLAIM about the product is earned — `production-ready`, `v1.0` — and it is the
only one pointed that way. In an unattended loop that makes it more necessary, not
less: a chain that ships without a person in it will eventually produce a maturity
claim nobody felt embarrassed writing.

Its rule is a LOCKED contract with ordered hard caps, named flags, a status
vocabulary and a freshness threshold. All of it mechanizable, none of it
mechanized until 2026-09-01 — so the gate that guards against a claim nobody
earned was itself a contract nobody enforced.

What these tests pin hardest is the refusal to infer. A missing manifest, a
missing rule, an empty evidence directory: each is `EVIDENCE_INSUFFICIENT` with
the flag that says which, and never a pass by default. A project that has not set
the gate up has not passed it.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_honesty_gate import (  # noqa: E402
    INSUFFICIENT, RUNNING, SUFFICIENT, WITH_CAVEATS, check, freshness_days, main,
)

_REPO = Path(__file__).resolve().parents[3]
TODAY = date(2026, 9, 1)


def _kit(root: Path, *, rule: bool = True, slug: str | None = "the-anchor",
         status: str = RUNNING, evidence: list[dict] | None = None,
         threshold: str = "`30 days`") -> Path:
    if rule:
        (root / "rules").mkdir(parents=True, exist_ok=True)
        (root / "rules" / "honesty-gate-golden-rule.md").write_text(
            f"# Dogfood Golden Rule\n\n**Freshness threshold (PER-PROJECT):** "
            f"{threshold} by default.\n", encoding="utf-8")
    hg = root / "records" / "honesty-gate"
    hg.mkdir(parents=True, exist_ok=True)
    if slug is not None:
        (hg / "manifest.md").write_text(
            f"# Manifest\n\n**Slug:** `{slug}`\n\n**Status:** `{status}`\n",
            encoding="utf-8")
    for i, item in enumerate(evidence or []):
        (hg / "evidence").mkdir(exist_ok=True)
        fields = {"scenario": slug, "date": TODAY.isoformat(), "operator": "paulo",
                  "outcome": "pass", "summary": "ran it"} | item
        body = "\n".join(f"{k}: {v}" for k, v in fields.items())
        (hg / "evidence" / f"e{i}.md").write_text(f"---\n{body}\n---\n\nrun\n",
                                                  encoding="utf-8")
    return root


# ── absence is never a pass ───────────────────────────────────────────────────


def test_no_golden_rule_is_insufficient(tmp_path: Path) -> None:
    """Without the contract that says what would count, nothing counts."""
    report = check(_kit(tmp_path, rule=False), today=TODAY)

    assert report.verdict == INSUFFICIENT
    assert report.hard_caps == ["golden_rule_missing"]


def test_no_manifest_is_insufficient_not_exempt(tmp_path: Path) -> None:
    (tmp_path / "rules").mkdir(parents=True)
    (tmp_path / "rules" / "honesty-gate-golden-rule.md").write_text("x", encoding="utf-8")

    report = check(tmp_path, today=TODAY)

    assert report.verdict == INSUFFICIENT
    assert "anchor_missing" in report.hard_caps


def test_a_manifest_with_no_slug_names_no_anchor(tmp_path: Path) -> None:
    _kit(tmp_path, slug=None)
    (tmp_path / "records" / "honesty-gate" / "manifest.md").write_text(
        "# Manifest\n\nSomething, but no anchor.\n", encoding="utf-8")

    assert check(tmp_path, today=TODAY).hard_caps == ["anchor_missing"]


# ── the status vocabulary is the rule's, and only one value passes ────────────


def test_only_running_satisfies_the_status_cap(tmp_path: Path) -> None:
    """`wired` means the anchor was invoked once. The bar is a team using it."""
    for status in ("planned", "wired", "paused", "abandoned"):
        report = check(_kit(tmp_path / status, status=status,
                            evidence=[{}]), today=TODAY)
        assert report.hard_caps == ["anchor_not_running"], status


def test_the_running_value_matches_the_locked_rule() -> None:
    """§ 2 is LOCKED. If the rule renames the value this constant mirrors, the two
    would disagree silently about what the bar is."""
    rule = (_REPO / "rules" / "honesty-gate-golden-rule.md").read_text(encoding="utf-8")

    assert f"`{RUNNING}`" in rule


# ── evidence must be for THIS anchor, complete, and recent ────────────────────


def test_evidence_for_another_scenario_does_not_count(tmp_path: Path) -> None:
    _kit(tmp_path, evidence=[{"scenario": "some-other-anchor"}])

    assert check(tmp_path, today=TODAY).hard_caps == ["no_anchor_evidence"]


def test_evidence_missing_a_locked_field_is_ignored(tmp_path: Path) -> None:
    """§ 5 says ignored, not rejected — a malformed note must not be louder than
    a missing one."""
    _kit(tmp_path, evidence=[{"operator": None}])
    path = next((tmp_path / "records" / "honesty-gate" / "evidence").glob("*.md"))
    path.write_text(path.read_text(encoding="utf-8").replace("operator: None\n", ""),
                    encoding="utf-8")

    assert check(tmp_path, today=TODAY).hard_caps == ["no_anchor_evidence"]


def test_stale_evidence_fails_the_freshness_cap(tmp_path: Path) -> None:
    old = (TODAY - timedelta(days=45)).isoformat()
    _kit(tmp_path, evidence=[{"date": old}])

    report = check(tmp_path, today=TODAY)

    assert report.hard_caps == ["anchor_evidence_stale"]
    assert "45 days old" in report.detail


def test_the_freshness_threshold_is_read_from_the_rule(tmp_path: Path) -> None:
    """The rule says the threshold is per-project and may be lowered freely. A
    number frozen in the script would override a project that lowered it."""
    old = (TODAY - timedelta(days=20)).isoformat()
    _kit(tmp_path, evidence=[{"date": old}], threshold="`7 days`")

    report = check(tmp_path, today=TODAY)

    assert report.freshness_days == 7
    assert report.hard_caps == ["anchor_evidence_stale"]


def test_freshness_falls_back_when_the_rule_states_no_number() -> None:
    assert freshness_days("no threshold declared here") == 30


# ── the soft caps, which permit the claim and travel with it ──────────────────


def test_thin_evidence_caps_at_caveats(tmp_path: Path) -> None:
    _kit(tmp_path, evidence=[{"outcome": "fail", "operator": "ana"},
                             {"operator": "paulo"}])

    report = check(tmp_path, today=TODAY)

    assert report.verdict == WITH_CAVEATS
    assert "thin_evidence" in report.soft_caps


def test_evidence_with_no_failure_story_caps_at_caveats(tmp_path: Path) -> None:
    """A dogfood without failures is theatre — the rule's own words."""
    _kit(tmp_path, evidence=[{"operator": "ana"}, {"operator": "bea"},
                             {"operator": "caio"}])

    report = check(tmp_path, today=TODAY)

    assert report.verdict == WITH_CAVEATS
    assert "no_failure_story" in report.soft_caps


def test_a_single_operator_caps_at_caveats(tmp_path: Path) -> None:
    """Avoids the one-person-who-knows-how syndrome the rule names."""
    _kit(tmp_path, evidence=[{}, {}, {"outcome": "partial"}])

    report = check(tmp_path, today=TODAY)

    assert report.verdict == WITH_CAVEATS
    assert report.soft_caps == ["single_operator"]


def test_full_evidence_is_sufficient(tmp_path: Path) -> None:
    _kit(tmp_path, evidence=[{"operator": "ana"}, {"operator": "bea"},
                             {"operator": "caio", "outcome": "fail"}])

    report = check(tmp_path, today=TODAY)

    assert report.verdict == SUFFICIENT
    assert report.soft_caps == []
    assert report.evidence_count == 3


# ── the exit codes a caller routes on ─────────────────────────────────────────


def test_exit_codes_distinguish_the_three_verdicts(tmp_path: Path) -> None:
    ok = _kit(tmp_path / "ok", evidence=[{"operator": "ana"}, {"operator": "bea"},
                                         {"operator": "caio", "outcome": "fail"}])
    caveats = _kit(tmp_path / "caveats", evidence=[{}])
    refused = _kit(tmp_path / "refused", status="wired", evidence=[{}])

    assert main(["--root", str(ok), "--today", TODAY.isoformat()]) == 0
    assert main(["--root", str(caveats), "--today", TODAY.isoformat()]) == 3
    assert main(["--root", str(refused), "--today", TODAY.isoformat()]) == 1


def test_an_unreadable_root_is_two_not_a_verdict(tmp_path: Path) -> None:
    assert main(["--root", str(tmp_path / "absent")]) == 2


def test_this_repository_has_not_claimed_what_it_cannot_show() -> None:
    """The kit declares no anchor, so it does not pass its own gate — and saying
    so is the point. A gate its author exempts himself from is decoration."""
    assert check(_REPO, today=TODAY).verdict == INSUFFICIENT
