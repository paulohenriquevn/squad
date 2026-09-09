"""Turning a `Report` into either dense text or JSON, in one place.

Dense text is the default because the primary reader of this CLI is an agent, and
ANSI colour in a transcript is context spent on decoration. There is no colour here
and no progress spinner; a TTY check would only decide between two things this module
does not offer.

The `not checked` block is rendered LAST and is never suppressed when empty — an
absent section reads as "nothing was missed", and that has to be stated rather than
implied.
"""
from __future__ import annotations

import json

from squad.cli.report import Report


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


def render_text(report: Report) -> str:
    out: list[str] = []
    if report.observed:
        out.append("observed: " + " · ".join(report.observed))
    out.extend(report.lines)
    if report.not_checked:
        out.append("")
        out.append(f"NOT CHECKED ({len(report.not_checked)}):")
        out.extend(f"  {item}" for item in report.not_checked)
    else:
        out.append("")
        out.append("NOT CHECKED: nothing — this command covered its whole subject")
    return "\n".join(out)


def emit(report: Report, *, as_json: bool) -> int:
    """Print the report and hand back its exit code for `main` to return."""
    print(render_json(report) if as_json else render_text(report))
    return report.exit_code
