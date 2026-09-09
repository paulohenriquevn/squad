"""The supervisor's two jobs run on their own clocks.

Measured 2026-09-04 on the runner: routes landed 51, 54 and 53 minutes apart
against a configured interval of 10. The loop ran route and land in series, and
land runs two full test suites per branch — so a lane that finished at 14:35 sat
idle until 15:22. `fleet_idle` put the window at **94% idle**.

Nothing was broken. Route is cheap and must be frequent; land is expensive and
must not decide how often route happens.
"""
import re
from pathlib import Path

import pytest

SUPERVISOR = Path(__file__).parent.parent / "mechanisms" / "fleet" / "fleet_supervisor.sh"


@pytest.fixture(scope="module")
def source() -> str:
    return SUPERVISOR.read_text()


def test_route_and_land_do_not_share_a_loop(source):
    """A single loop makes the slow job set the fast job's period."""
    body = re.search(r"(?ms)^while :; do.*?^done", source)
    if body is None:
        # Two loops is the fix; one combined loop is the defect.
        assert source.count("fleet_router.py") >= 1
        return
    one_loop = body.group(0)
    has_route = "fleet_router.py" in one_loop
    has_land = "fleet_lander.py" in one_loop
    assert not (has_route and has_land), (
        "route and land share a loop, so land's runtime becomes route's period — "
        "measured 51-54 minutes between routes against a 10-minute interval"
    )


def test_the_route_interval_is_under_the_idle_ceiling(source):
    """A lane may not sit idle longer than the ceiling the operator set."""
    match = re.search(r"ROUTE_INTERVAL=\$\{ROUTE_INTERVAL:-(\d+)\}", source)
    assert match, "the route loop must carry its own interval, separate from land's"
    assert int(match.group(1)) <= 300, (
        f"route every {match.group(1)}s leaves a lane idle longer than the "
        f"300s ceiling; the whole point of splitting the loops is this number"
    )


def test_land_still_runs(source):
    """Splitting the loops must not drop the half that protects the branch."""
    assert "fleet_lander.py" in source


def test_the_two_loops_are_supervised_together(source):
    """If one loop dies the supervisor must not look alive on the strength of
    the other. A half-dead supervisor that still prints is worse than a dead
    one — this kit's most-found defect, an inability to work published as work."""
    assert "wait" in source, "the shell must wait on both background loops"
