#!/usr/bin/env python3
"""Build an isolated sandbox for one Squad skill eval.

Every eval needs a workspace that looks like an adopted umbrella: a populated
`BACKLOG.md`, the rules the skill reads, the agents it routes to, and the scripts its
gates call. Without one, each subagent improvises a different environment and the runs
stop being comparable — a with-skill run that had a registry and a baseline that did not
differ by the fixture, not by the skill.

The sandbox is a COPY. Runs must never touch the real repo: a skill under test writes to
BACKLOG.md, and an eval that mutates the source would poison every subsequent run in the
same batch, silently and in run order.

Usage:
    python3 setup_squad_eval_sandbox.py <dest-dir> [--with-plan SLUG]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
FIXTURE_BACKLOG = REPO / "skills" / "backlog-item" / "evals" / "fixtures" / "BACKLOG.md"
# A governed repo with REAL code, so measurement evals have something to open, count and
# cite. An eval whose target does not exist tests the agent's imagination, not the skill.
FIXTURE_REPO = REPO / "skills" / "discover-execute" / "evals" / "fixtures" / "theo-lens"

# What a Squad skill reads at runtime. Copied wholesale rather than cherry-picked: a
# missing rule makes a skill fail in a way that looks like a skill defect.
COPY_DIRS = ["rules", "agents", "scripts"]
COPY_SKILLS = [
    "backlog-item", "backlog-init", "backlog-review",
    "discover-plan", "discover-edge-cases", "discover-plan-confidence",
    "discover-execute", "discover-confidence", "discover-improve",
]


def build(dest: Path, with_plan: str | None = None, baseline: bool = False) -> None:
    """Build the sandbox. `baseline=True` omits the Squad system entirely.

    This distinction is the whole validity of the comparison. A first run copied `rules/`
    and `skills/` into BOTH configurations, and the without-skill agents read
    `rules/cycle-backlog.md`, cited G2 and G5 by name, and produced near-identical
    behaviour. That is not a baseline — it measures "was told to read the SKILL.md" against
    "found the contract anyway", and both arms had the system.

    A baseline sandbox therefore carries only the registry and the CHANGELOG: what someone
    inherits when they open a workspace with no Squad installed. The schema is still
    inferable from the existing items, which is realistic and fair.
    """
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    if not baseline:
        for d in COPY_DIRS:
            src = REPO / d
            if src.is_dir():
                shutil.copytree(src, dest / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        skills_dest = dest / "skills"
        skills_dest.mkdir()
        for s in COPY_SKILLS:
            src = REPO / "skills" / s
            if src.is_dir():
                shutil.copytree(src, skills_dest / s, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests"))

    shutil.copy2(FIXTURE_BACKLOG, dest / "BACKLOG.md")

    # CHANGELOG.md is a pre-flight requirement in several skills (Unbreakable Rule 6).
    (dest / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n### Added\n\n### Fixed\n", encoding="utf-8"
    )

    for sub in ("discoveries/plans", "discoveries/opportunities", "backlog", "reviews"):
        (dest / "knowledge-base" / sub).mkdir(parents=True, exist_ok=True)

    # Make it a git repo: skills walk up looking for .git or .claude to find the root, and
    # without a marker they resolve to somewhere outside the sandbox.
    (dest / ".git").mkdir()

    if FIXTURE_REPO.is_dir():
        shutil.copytree(FIXTURE_REPO, dest / "theo-lens",
                        ignore=shutil.ignore_patterns("__pycache__", "node_modules"))

    if with_plan:
        _write_plan(dest, with_plan)

    print(f"sandbox: {dest}")
    print(f"  BACKLOG.md items: {(dest / 'BACKLOG.md').read_text(encoding='utf-8').count(chr(10) + '## B-')}")
    if baseline:
        print("  baseline: no rules/, no skills/ — registry only")
    else:
        print(f"  rules: {len(list((dest / 'rules').glob('*')))} · agents: {len(list((dest / 'agents').glob('*.md')))}")
    if (dest / "theo-lens").is_dir():
        print("  governed repo: theo-lens (real N+1 in src/api/traces.ts)")
    if with_plan:
        print(f"  plan: knowledge-base/discoveries/plans/{with_plan}-plan.md")


def _write_plan(dest: Path, slug: str) -> None:
    """A scored measurement plan, for evals that start at /discover-execute."""
    plan = dest / "knowledge-base" / "discoveries" / "plans" / f"{slug}-plan.md"
    plan.write_text(
        "# Measurement Plan: round-trips do listing de traces\n\n"
        "**Item:** B-014\n"
        "**Repo:** theo-lens\n"
        "**Mode:** review\n"
        f"**Slug:** `{slug}`\n"
        "**Created:** 2026-08-05\n\n"
        "## Context\n\n"
        "O dashboard passou a carregar 30 dias por padrão e a listagem ficou mais lenta.\n\n"
        "## Hypothesis\n\n"
        "O endpoint de listagem emite uma query por span, então um trace de 200 spans custa\n"
        "200 round-trips ao Postgres.\n\n"
        "## Falsification\n\n"
        "Se o endpoint emitir uma query só, independente da contagem de spans, a hipótese\n"
        "está morta e B-014 é encerrado com esse resultado como `kill_reason`.\n\n"
        "Um resultado parcial não a resgata: a afirmação é sobre o padrão de acesso, não\n"
        "sobre encontrar uma query lenta qualquer.\n\n"
        "## Measurement Questions\n\n"
        "| # | Question | Corner | Tool | Target | Expected answer shape |\n"
        "|---|---|---|---|---|---|\n"
        "| Q1 | Quantas queries o handler emite por request? | evidence | Read | `theo-lens/src/api/traces.ts` | contagem + file:line |\n"
        "| Q2 | O que mais consome esse handler? | blast_radius | Grep | `theo-lens/src/` | lista de chamadores |\n"
        "| Q3 | Como saberemos que o fix funcionou? | verification | Read | `theo-lens/src/api/traces.ts` | critério pass/fail |\n\n"
        "<!-- DEFER-CORNER: constraint | current-constraint.md está undeclared -->\n\n"
        "## Halt-loop Checkpoints\n\n"
        "| Checkpoint | Assertion | Action if fails |\n"
        "|---|---|---|\n"
        "| Antes de responder Qx | o alvo citado abre e a linha existe | marcar Qx BLOCKED |\n"
        "| Toda iteração | reler `## Falsification` — já foi satisfeito? | parar e matar o item |\n\n"
        "## Acceptance Criteria\n\n"
        "- [ ] Toda pergunta respondida ou BLOCKED com razão\n"
        "- [ ] O critério de falseamento foi avaliado explicitamente\n",
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a Squad eval sandbox.")
    ap.add_argument("dest", type=Path)
    ap.add_argument("--with-plan", default=None, help="also write a scored measurement plan with this slug")
    ap.add_argument("--baseline", action="store_true", help="omit rules/ and skills/ — the without-skill arm")
    args = ap.parse_args()

    if not FIXTURE_BACKLOG.is_file():
        print(f"FATAL: fixture missing at {FIXTURE_BACKLOG}", file=sys.stderr)
        return 2

    build(args.dest.resolve(), args.with_plan, baseline=args.baseline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
