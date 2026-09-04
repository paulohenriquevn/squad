# Hooks

9 defensive runtime hooks that enforce safety invariants at the shell level.
Claude Code executes these automatically at specific lifecycle events, as wired
in `settings.json`.

## Shared Library

`squad.layout` — imported by every hook that needs the ecosystem path. It replaced
`environment/detect-layout.sh` when the hooks became Python; nothing sources shell
for layout any more.
Sets `$ECO` (`.claude` or `.`) and `$PROJECT_DIR`.

## Hook Inventory

| Hook | Event | Behavior | Exit |
|---|---|---|---|
| `sessionstart-context.py` | SessionStart | Injects git branch, active plan, loop state | 0 always |
| `userpromptsubmit-inject.py` | UserPromptSubmit | Injects active plan excerpt + SHA256 attestation check | 0 always |
| `validate-command.py` | PreToolUse (Bash) | Blocks destructive git ops, rm -rf on system paths, read-only boundary | 0=allow, 2=block |
| `boundary-check.py` | PreToolUse (Edit/Write) | Blocks writes to study-material/ | 0=allow, 2=block |
| `post-edit-check.py` | PostToolUse (Edit/Write) | Multi-language linter feedback | 0 always |
| `public-copy-lint.py` | PostToolUse (Edit/Write) | Bans unverified production claims in README | 0 always (advisory) |
| `english-only-check.py` | PostToolUse (Edit/Write) | Reports non-English prose in the edited file (rules/english-only.md) | 0 always (advisory) |
| `stop-validation.py` | Stop | CHANGELOG gate (HARD), secret leak gate (HARD), TDD gate (warn) | 0=clean, 2=block |
| `precompact-preserve.py` | PreCompact | Snapshots plan + progress before context compaction | 0 always |

The prior-art study zone under `records/references/` was retired on 2026-09-01
and is no longer guarded by any hook — a consumer still holding material there
must move it (`rules/reference-provenance.md`).

## Design Principles

- Every hook uses `set -euo pipefail` (fail-fast)
- Hard gates exit 2; advisory gates exit 0 with stderr output
- JSON output follows `hookSpecificOutput.additionalContext` convention
- Each hook has **single responsibility** (SRP)

## Adding a New Hook

1. Create `hooks/{name}.sh` with `#!/bin/bash` and `set -euo pipefail`
2. `from squad.layout import resolve` for ecosystem detection
3. Wire in `settings.json` under the appropriate event
4. Add tests in `tests/hooks/test_{name}.sh`
5. Document exit codes in the script header
