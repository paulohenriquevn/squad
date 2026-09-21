# Hooks

9 defensive runtime hooks that enforce safety invariants outside the agent's
turn. Claude Code executes these automatically at specific lifecycle events,
wired in `hooks/hooks.json` (plugin layout) and `settings.json` (copy layout) —
both, or the hook runs in one install shape and not the other.

## Shared Library

The hooks are Python and import `squad/`, which replaced the shell helpers under
`environment/`. Nothing sources shell for layout any more, and no hook sets an
environment variable for another to read.

| Module | Answers |
|---|---|
| `squad` | the wire format: one typed context per event, and the verbs each event may reply with. An unreadable payload BLOCKS |
| `squad.layout` | where the kit's code is and where the cycle's data goes — `plugin`, `copy` or `standalone`. Returns a `Layout`, never a variable |
| `squad.plan` | which plan is active, how it was found, and whether it still matches its attestation |
| `squad.boundaries` | where the installed kit ends and the project begins. Asked by `boundary-check` for `Edit`/`Write` and by `validate-command` for the shell, so one boundary cannot hold against one tool and not the other |
| `squad.public_copy` | which claims measurement has not earned. Asked by `public-copy-lint` after an edit and by `stop-validation` at the end of the session |

## Hook Inventory

| Hook | Event | Behavior | Exit |
|---|---|---|---|
| `sessionstart-context.py` | SessionStart | Injects git branch, active plan, loop state | 0 always |
| `userpromptsubmit-inject.py` | UserPromptSubmit | Injects active plan excerpt + SHA256 attestation check | 0 always |
| `validate-command.py` | PreToolUse (Bash) | Blocks destructive git ops, deletion of a permanent branch, rm -rf on system paths, shell reads of credential paths, and shell writes into `.squad/study-material/` or the installed kit | 0=allow, 2=block |
| `boundary-check.py` | PreToolUse (Edit/Write) | Blocks writes to `.squad/study-material/` and into the installed kit — the same line `validate-command` holds against the shell | 0=allow, 2=block |
| `post-edit-check.py` | PostToolUse (Edit/Write) | Multi-language linter feedback | 0 always |
| `public-copy-lint.py` | PostToolUse (Edit/Write) | Bans unverified production claims in README | 0 always (advisory) |
| `english-only-check.py` | PostToolUse (Edit/Write) | Reports non-English prose in the edited file (rules/english-only.md) | 0 always (advisory) |
| `stop-validation.py` | Stop | CHANGELOG gate (HARD), secret leak gate (HARD), TDD gate (warn), public-copy claims (warn). Blocks once — the second attempt reports and lets the session end | 0=clean, 2=block |
| `precompact-preserve.py` | PreCompact | Snapshots plan + progress before context compaction | 0 always |

The prior-art study zone under `records/references/` was retired on 2026-09-01  <!-- write-path: names the retired zone to record that it was retired -->
and is no longer guarded by any hook — a consumer still holding material there
must move it (`rules/reference-provenance.md`).

## Design Principles

- **An inability to measure never becomes a passing measurement.** A payload that
  cannot be parsed exits 2 (`squad/__init__.py`); a gate that could not run says
  so rather than returning the same silence as a gate that ran and found nothing.
- **Hard gates exit 2; advisory gates exit 0** and write to stdout. `reason` is
  read by Claude, `systemMessage` by the person — they are not interchangeable.
- **A gate fires once.** A Stop hook that refuses every attempt leaves the session
  no exit, so `stop_hook_active` degrades the blockers to warnings on the second
  pass. The finding is still reported in full.
- **A subprocess may not outlive its hook.** Each hook that shells out declares
  `*_TIMEOUT` constants that fit inside the budget `hooks.json` gives it, with
  room for the calls that run after. Being killed by the runtime is the one
  failure a hook cannot record, because the process that would write the note is
  the one that died. `tests/hooks/test_hook_time_budget.py` does the arithmetic.
- **One rule, one definition.** Two hooks enforcing the same rule read it from
  `squad/`; a second copy is how the halves drift apart, and both times it
  happened here the smaller copy was the one that ran last.
- Each hook has **single responsibility** (SRP).

## Adding a New Hook

1. Create `hooks/{name}.py` with `#!/usr/bin/env python3`.
2. `c = create_context(XContext)` from `squad` — never parse stdin by hand.
   Reach for `squad.layout.resolve()` when the hook needs the kit or the project.
3. Declare a `*_TIMEOUT` constant for anything you spawn, sized against the
   budget you are about to give the hook.
4. Wire it in **both** `hooks/hooks.json` (plugin layout) and `settings.json`
   (copy layout) — `tests/test_hook_declarations_agree.py` fails if you wire only
   one, which is how a hook shipped complete and was never invoked.
5. Add tests in `tests/hooks/test_{name}.py`, addressed by hook NAME through
   `tests/hook_harness.py` so the contract survives the implementation.
6. Add the row to the table above and update the count line; the same test
   checks both against `hooks/*.py`.
7. Document exit codes in the script header.
