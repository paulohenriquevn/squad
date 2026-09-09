# Loop Engine Convention

Decision rule for picking between Skill, Agent (subagent), and ralph-loop (halt-loop). Use the smallest tool that does the job.

## The three engines

| Engine | What it is | Cost shape | Reuses context? |
|---|---|---|---|
| **Skill** | A named prompt/procedure invoked by Claude in the main conversation | Cheap | Yes — runs in main context |
| **Agent (subagent)** | A sandboxed sub-conversation with its own context window | Medium | No — fresh context |
| **ralph-loop (halt-loop)** | An autonomous iterative loop with a completion promise | Most expensive | Partial — preserved via PreCompact + session-catchup |

## Decision rule

1. **Single-step, deterministic, fits in main context** → Skill.
2. **Multi-step research or work where main-context bloat is a concern** → Agent.
3. **Iterative work that needs to keep running until a completion promise is met** → ralph-loop.

## When Skill is right

- The work is one procedure that produces one output.
- You want the result back in the main conversation (e.g., for follow-up).
- The work doesn't generate so much output that it'll pollute main context.

## When Agent is right

- You'd run many Grep/Read calls — let the agent do them in its sandbox and return the summary.
- The task is independent of the main thread's recent context.
- You want fresh eyes (e.g., independent review).

## When ralph-loop is right

- The work is iterative with a clear completion criterion ("until tests pass", "until plan tasks done").
- The task warrants unattended execution — you accept handing control to the loop until it emits a completion promise.
- The completion promise is a phrase the loop can emit on success (e.g., `IMPLEMENTATION_COMPLETE`, `REVIEW_READY_TO_MERGE`).

## How to invoke ralph-loop:ralph-loop safely

**The positional prompt is shell-evaluated.** Inlining a multi-section driver
prompt — backticks, fenced code blocks, `$(...)` — breaks loop startup with a
bash parse error, before a single iteration runs.

**The same hazard has a second door, and it fails quietly instead of loudly.**
Long text sent through `ssh host "… <<'QUOTED' …"` is read by the LOCAL shell
before the remote heredoc protects anything, so backticked words are executed
here and arrive as empty strings. The command succeeds, the file is written, and
two words are missing from the middle of a sentence. Measured five times across
2026-09-04 and 05 by a coordinator driving a remote host — the last one while
writing a comment about avoiding it, which is how well "remember to escape"
works as a control.

So the rule is not about the loop. It is: **text with shell metacharacters goes
to a file that is copied, never through a command line.** `scp` the file and run
the file; the loop's positional prompt below is one instance of that, not the
statement of it.

So the prompt goes to a file and the positional argument points at it:

1. Write the substituted prompt to `.claude/halt-loop-prompts/{skill}-{slug}.md`
   (gitignored — it is one invocation's driver, not a versioned artifact).
2. Invoke with a positional prompt carrying **no shell metacharacters**:
   `Read .claude/halt-loop-prompts/{skill}-{slug}.md and follow its instructions
   for this halt-loop iteration.`
3. Pass the completion promise as its own flag: `--completion-promise 'TOKEN'`.

Written down here on 2026-08-31 because it was not. Three skills —
`/implement`, `/discover-execute` and `/plan-improve` — each opened their loop
step with *"Read `loop-engine-convention.md § How to invoke ralph-loop:ralph-loop
safely` BEFORE this step"*, and **this section did not exist**. Each then restated
the shell-evaluation fact in its own words, so one piece of knowledge lived in
three places and its named home was empty. The skills keep their one-line
summary; the rule is now the place it is summarised FROM.

## Anti-patterns

- Using a ralph-loop for a one-step task. A direct Skill invocation is simpler and traceable.
- Spawning 5 agents in parallel when one Grep would answer the question.
- Running a Skill for work that bloats main context with thousands of lines. Use an Agent.
- Multiple concurrent ralph-loops on overlapping state. They will conflict.

## State files

- ralph-loop persists its state in `ralph-loop.local.md` (slug, iteration, completion promise, start time).
- If a loop is stale (no progress for > 24h and `active: true`), treat it as abandoned and either cancel (`/ralph-loop:cancel-ralph`) or delete the state file.
