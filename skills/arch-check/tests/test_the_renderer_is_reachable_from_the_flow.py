"""The generator whose whole reason for existing is that hand-translation failed.

`emit_config.py` renders a ratified proposal into `.go-arch-lint.yml`. Its docstring
names four consecutive hand-adoption failures against `control-plane`, each of which
reported GREEN having validated nothing. Nothing invoked it: the only two mentions in
the whole tree were its own usage string and its own test, while SKILL.md's "Adopting
a proposal" told the human to "write the config in the linter's own format" by hand —
the exact step that failed four times.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SKILL = (_ROOT / "skills" / "arch-check" / "SKILL.md").read_text(encoding="utf-8")


def test_the_adoption_steps_name_the_renderer() -> None:
    section = _SKILL.split("## Adopting a proposal", 1)[1].split("\n## ", 1)[0]

    assert "emit_config.py" in section, (
        "the adoption steps still send the reader to hand-translate")


def test_the_refusal_list_no_longer_reads_as_forbidding_it() -> None:
    """"You ask it to write a config" made the renderer look out of bounds."""
    refusals = _SKILL.split("## Refuses when", 1)[1]

    assert "You ask it to write a config: it proposes, you ratify." not in refusals
