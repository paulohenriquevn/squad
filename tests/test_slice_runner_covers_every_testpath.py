"""The runner CI uses must collect every test path the project declares.

`pyproject.toml` sets `testpaths = ["tests", "hooks/tests", "squad/tests"]`, and its
comment says exactly why the last two are there:

    "`hooks/tests` and `squad/tests` are here because they were NOT, and nothing said
    so: fourteen tests for `stop-validation` and the whole hook library sat outside
    the collected set. A test the suite does not collect is a test that passed once."

`run_slice_tests.sh` then passed `tests` to pytest EXPLICITLY, and an explicit path
suppresses `testpaths` — so the two paths added to close that hole fell straight back
out of it. Measured 2026-09-09: a bare `pytest` collects 1894, `pytest tests` collects
1742, and the 152 in between never ran in CI, because `ci.yml` runs this script and
nothing else.

The hole was reopened by an optimisation, not by neglect: `ci.yml:132-134` records that
a second root-suite step was removed in 2026-08-26 to save "45s duplicated per run".
That step was the only bare `pytest` in the pipeline.

This asserts the relationship rather than the number, so a testpath added later is
covered without anyone remembering this file exists.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "mechanisms" / "cycle" / "run_slice_tests.sh"

#: `tomllib` is 3.11+, and this project supports 3.10 (`requires-python`). Reading one
#: known key with a regex costs less than a dependency, and the failure mode is loud:
#: no match raises rather than returning an empty list, which would make every
#: assertion below vacuously true.
_TESTPATHS_RE = re.compile(r"^testpaths\s*=\s*\[(.*?)\]", re.M | re.S)


def _declared_testpaths() -> list[str]:
    match = _TESTPATHS_RE.search((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert match, "pyproject.toml declares no `testpaths`; this test cannot judge without it"
    paths = re.findall(r'"([^"]+)"', match.group(1))
    assert paths, "`testpaths` parsed as empty — refusing to pass on an unread declaration"
    return paths


def test_every_declared_testpath_is_named_by_the_runner() -> None:
    """Each path in `testpaths` appears in the script that CI actually runs."""
    source = RUNNER.read_text(encoding="utf-8")
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    missing = [p for p in _declared_testpaths() if p not in code]
    assert not missing, (
        f"{missing} declared in pyproject `testpaths` and never passed to pytest by "
        f"{RUNNER.relative_to(ROOT)}. An explicit path argument suppresses `testpaths`, "
        f"so these collect in a bare `pytest` and NOT in the run CI performs."
    )


def test_the_declared_testpaths_are_the_ones_that_exist() -> None:
    """A testpath naming a directory nobody has is a claim, not coverage."""
    absent = [p for p in _declared_testpaths() if not (ROOT / p).is_dir()]
    assert not absent, f"testpaths names {absent}, which do not exist on disk"
