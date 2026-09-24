"""Work in flight is an open EVENT. A status is a position in the chain.

Three readers answered "what is in flight" and no two of them the same way:

    board_state._wip              items INSIDE a phase — started and not ended, from the
                                  event stream. Its own docstring: "WIP is not a card
                                  count"
    backlog_index.BUCKETS         `approved` + `planned`, from STATUS, reading zero events
    select_backlog_item.in_flight `planned` alone, from STATUS

The two status readers disagree with each other about `approved`, and each has a measured
reason: the index puts it in because a commitment does not belong in the same count as a
hunch nobody has read, and the selector keeps it out because `awaiting_plan` and
`in_flight` hand work to different phases.

Reported by a consumer whose panel said six items were in flight while zero phases were
open: five were commitments never started and one was merged waiting for a tag. Their user
read the panel and asked whether work was happening in a batch — a reasonable question,
because the label said so. And `cycle-maintenance.md` makes *exactly one item in flight* a
hard gate, so nobody could tell a violated invariant from a mislabelled bucket without
opening the generator.

THE FIX IS THE LABEL, NOT THE GROUPING. The index groups by COMMITMENT — nobody decided,
somebody decided, it ended — and that grouping is right and useful. What it cannot know
from status is whether anything is happening. So the word belongs to the readers that have
the stream, and this test keeps it there.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "skills" / "backlog-review" / "scripts"))

import backlog_index  # noqa: E402

#: Files that may say "in flight" because they read the event stream, or because they are
#: quoting this history. Everything else derives from status and must not claim activity.
_MAY_CLAIM_ACTIVITY = {
    "skills/backlog-review/scripts/board_state.py",       # computes it from the stream
    "skills/backlog-review/scripts/select_backlog_item.py",  # `planned` only, and says so
    "tests/test_in_flight_is_not_derived_from_status.py",
    "CHANGELOG.md",
}

_PHRASE = re.compile(r"in[- ]flight", re.IGNORECASE)


def test_the_index_does_not_label_a_status_bucket_in_flight() -> None:
    labels = " ".join(backlog_index.BUCKET_LABEL.values())
    assert not _PHRASE.search(labels), (
        f"a bucket fed only by status is labelled {labels!r}. It cannot know whether "
        "anything is happening: an item sits at `approved` for days without a phase ever "
        "opening")
    assert not any(_PHRASE.search(k) for k in backlog_index.BUCKETS.values()), (
        f"the bucket KEY still says it: {sorted(set(backlog_index.BUCKETS.values()))}")


def test_the_grouping_itself_is_unchanged() -> None:
    """The label was wrong; the three groups were not.

    `approved` stays with `planned`, on the index's own argument: a commitment does not
    belong in the same count as a hunch nobody has read.
    """
    by_bucket: dict[str, set[str]] = {}
    for status, bucket in backlog_index.BUCKETS.items():
        by_bucket.setdefault(bucket, set()).add(status)
    assert by_bucket == {
        "open": {"raw", "triaged"},
        "committed": {"approved", "planned"},
        "closed": {"shipped", "killed"},
    }, by_bucket


def test_the_contract_names_every_status_in_a_bucket() -> None:
    """The rule's table covered five of six. `approved` was in no bucket at all."""
    rule = (_ROOT / "rules" / "cycle-backlog.md").read_text(encoding="utf-8")
    section = rule.split("## Index", 1)[-1].split("\n## ", 1)[0]
    for status in backlog_index.BUCKETS:
        assert f"`{status}`" in section, (
            f"`{status}` is in a bucket in the code and in none in the contract, so a "
            "reader consulting the rule cannot predict where the index puts it")


def test_no_status_derived_reader_claims_activity() -> None:
    """The guard against doing this again in a fourth place.

    It inspects the MAPPINGS, not the prose. The first draft grepped each file for the
    phrase and flagged `backlog_index.py` itself — for the paragraph explaining why it
    stopped using the word. A file is allowed to name the vocabulary it retired; what it
    may not do is bucket a status under it.
    """
    import importlib
    import pkgutil

    scripts = _ROOT / "skills" / "backlog-review" / "scripts"
    offenders = []
    for mod in pkgutil.iter_modules([str(scripts)]):
        try:
            m = importlib.import_module(mod.name)
        except Exception:  # noqa: BLE001 — a module that will not import is another test's
            continue
        for attr in ("BUCKETS", "BUCKET_ORDER", "BUCKET_LABEL"):
            value = getattr(m, attr, None)
            if value is None:
                continue
            names = (list(value.values()) + list(value)) if isinstance(value, dict) else list(value)
            hits = [n for n in names if isinstance(n, str) and _PHRASE.search(n)]
            if hits:
                offenders.append(f"{mod.name}.{attr}: {hits}")
    assert not offenders, (
        "these group by status and name a bucket with the activity vocabulary: "
        + "; ".join(offenders))
