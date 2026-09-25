"""The commands an acceptance criterion names to prove itself — ONE list, read by both
checkers in this skill.

`score_alignment._EXECUTABLE_RE` grades a criterion executable when it names one of these;
`check_criteria_discriminate._ALLOWED_COMMANDS` runs a criterion only when its commands are
allowlisted. They held two lists until #167, and the lists excluded each other:

    pnpm vitest run x.test.ts    scorer: executable       executor: REFUSED
    npx vitest run x.test.ts     scorer: NOT executable   executor: runs

In a pnpm monorepo no real command satisfied both, and the workaround an author found was
writing `npx` AND `exit 0` in one bullet — fitting the text to two instruments by two
paths. The same shape `squad/signoff.py` and `squad/boundaries.py` exist to close: one
reader per question.

The basename is deliberately specific. Every skill ships its scripts as loose modules on
one `sys.path`, and two slices holding a `commands.py` would shadow each other under one
pytest process.
"""
from __future__ import annotations

#: Package managers, test runners and interpreters a criterion runs its proof with. The
#: executor allowlists every one of these, and the scorer grades a criterion naming one
#: as executable.
#:
#: `pnpm` and `yarn` run package scripts exactly as `npm` and `npx` do, and those two were
#: already trusted to run unattended; admitting them is consistency with that decision,
#: not a new one. A project's own `package.json` scripts are what any of the four runs.
RUNNERS = (
    "npm", "npx", "pnpm", "yarn", "node",
    "pytest", "python3",
    "go", "cargo", "make",
    "bash", "grep",
)

#: Named by a criterion as something that runs, and NOT run by the executor. `curl`
#: proves a criterion by reaching a network, which `check_criteria_discriminate` refuses
#: to do unattended — so the scorer still counts it as executable, and the executor
#: reports it `NOT RUN` rather than unverified-and-sound. Declared here so the divergence
#: is a decision a test holds, not a drift nobody sees.
NAMED_NOT_RUN = ("curl",)
