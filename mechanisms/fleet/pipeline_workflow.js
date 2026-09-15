export const meta = {
  name: 'backlog-pipeline',
  description: 'Advance N backlog items through the cycle concurrently, one stage each',
  whenToUse: 'When a consumer has several triaged items waiting and the phases would otherwise sit idle between them',
  phases: [
    { title: 'Discover', detail: 'measure each item against the code, in its own worktree' },
    { title: 'Align',    detail: 'write and score an alignment brief per item' },
    { title: 'Judge',    detail: 'a reviewer who is not the author signs the brief, or refuses' },
    { title: 'Plan',     detail: 'only for items whose brief carries a signature' },
    { title: 'Implement', detail: 'the first writing stage: its own worktree, RED before GREEN' },
  ],
}

// The stage prompts are NOT in this file. `skills/pipeline/scripts/spawn_stages.py`
// instantiates `skills/pipeline/templates/stage-*.md` into a per-item directory
// that lives in git, and this script reads them.
//
// The first run kept them inline and it cost the audit trail: six agents ran over
// a real backlog, three of them found defects in this kit — one located an id
// collision in score_alignment.py with line numbers — and NOT ONE of their
// prompts is recoverable. The transcript records what they said; nothing recorded
// what they were asked.
//
// Read-only is enforced by the generated frontmatter's tool list, not by a
// sentence. The first run asked in prose, which the harness does not read.
// The queue is NOT a literal here, and must not become one again. Workflow scripts
// have no filesystem access, so this file cannot read BACKLOG.md — the caller runs
//
//   python3 skills/backlog-review/scripts/select_backlog_item.py BACKLOG.md --json
//
// and passes `queue` through args. That is what applies the maintenance chain's
// ranking (triaged before raw, then oldest first) and, crucially, drops blocked
// items: an item waiting on another reads `triaged` on disk and cannot be worked on.
//
// The literal that used to sit here was ['B-001', 'B-022', 'B-033'], and B-001 is
// blocked on a sponsor decision in the very registry it was pointed at. A hand-kept
// list cannot know that, and it went unnoticed for a whole run.
// `queue` ALONE is not the work. SELECT emits three keys that carry items a stage can
// act on, and each was added because a scheduler reading only the previous ones could
// not see most of the registry:
//
//   queue          triaged and raw — DISCOVER has not run
//   awaiting_plan  approved — DISCOVER ran, PLAN has not
//   in_flight      planned — work started
//
// Measured on a consumer 2026-09-15, 102 items: passing the whole selection builds 71
// items, of which 56 approved enter at PLAN; passing the `queue` array this file used to
// demand builds 13, none of them approved. So an operator following the documented
// procedure exactly reproduced a bug the Python side no longer had — the code fix landed
// and the procedure that invokes it still prescribed the defect.
//
// `args.selection` is the whole object from `--json`. `args.queue` still works and is
// what every existing caller passes, but it schedules only a third of the registry.
const SELECTION = args?.selection
const ITEMS = Array.isArray(args?.items) ? args.items
  : SELECTION ? [...(SELECTION.queue ?? []),
                 ...(SELECTION.awaiting_plan ?? []),
                 ...(SELECTION.in_flight ?? [])]
  : args?.queue
if (!Array.isArray(ITEMS) || ITEMS.length === 0) {
  throw new Error(
    'no items: pass args.selection — the whole object from ' +
    '`select_backlog_item.py --json`. Passing args.queue alone schedules only the ' +
    'items DISCOVER has not reached, which on a real registry is a fraction of it. ' +
    'A literal list cannot know which items the registry says are blocked.')
}
// No default. A hardcoded path is one machine's, and this file is versioned and
// shipped to every consumer: the previous default named a workstation's home
// directory AND the origin ecosystem, and travelled into an adopter's history
// where it was found by THEIR publish-hygiene gate, not by ours.
const REPO = args?.repo
if (!REPO) {
  throw new Error(
    'no repo: pass args.repo. There is no sensible default — the workflow runs ' +
    'against whichever project invoked it, and a path baked in here would be ' +
    'the author\'s machine.')
}
const AGENTS = args?.agentsDir ?? 'records/pipeline-agents'

// The generated file IS the system prompt; the task line is all this script adds.
const stagePrompt = (item, stage, task) =>
  `Read and obey ${AGENTS}/${item.toLowerCase()}/${stage}.md — it is your ` +
  `instruction, written to disk before this run and versioned so a wrong ` +
  `finding can be traced to the prompt that produced it.\n\n${task}`

const BRIEF = {
  type: 'object',
  required: ['slug', 'evidence_found', 'summary'],
  properties: {
    slug: { type: 'string' },
    evidence_found: { type: 'boolean' },
    summary: { type: 'string' },
    files_examined: { type: 'array', items: { type: 'string' } },
  },
}

const JUDGEMENT = {
  type: 'object',
  required: ['slug', 'verdict', 'exit_code'],
  properties: {
    slug: { type: 'string' },
    // What `alignment_judge.py` was actually run with. Not a paraphrase of it.
    verdict: { type: 'string', enum: ['signed', 'refused'] },
    // The scorer's own exit code, measured by the judge rather than reported to
    // it. 0 permits, 1 forbids, and a high percentage with exit 1 is a refusal.
    exit_code: { type: 'integer' },
    reason: { type: 'string' },
    gaps: { type: 'array', items: { type: 'string' } },
  },
}

// PLAN returns structure now, not prose. IMPLEMENT is gated on what it produced,
// and a gate cannot read a paragraph: the scheduler needs to know whether there
// are tasks at all before it hands the item to an agent that writes.
const OUTLINE = {
  type: 'object',
  required: ['slug', 'tasks'],
  properties: {
    slug: { type: 'string' },
    tasks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['title', 'tdd'],
        properties: {
          title: { type: 'string' },
          // The RED shape this task can be driven from — an assertion, a GWT, or
          // a `test_<behavior>` literal. `check_tdd_shape.py` is what judges it,
          // and IMPLEMENT runs that itself rather than trusting this field.
          tdd: { type: 'string' },
        },
      },
    },
    unanswered: { type: 'array', items: { type: 'string' } },
  },
}

const IMPLEMENTED = {
  type: 'object',
  required: ['slug', 'branch', 'tasks_done', 'tasks_total'],
  properties: {
    slug: { type: 'string' },
    branch: { type: 'string' },
    worktree: { type: 'string' },
    tasks_done: { type: 'integer' },
    tasks_total: { type: 'integer' },
    // Both runs, not a claim about them: the test must be seen to fail before
    // the change and pass after, or it is a test written to fit the code.
    red_evidence: { type: 'string' },
    green_evidence: { type: 'string' },
    files_touched: { type: 'array', items: { type: 'string' } },
    not_done: { type: 'array', items: { type: 'string' } },
    blocked_by: { type: 'string' },
  },
}

const SCORE = {
  type: 'object',
  required: ['slug', 'machine_ratio', 'verdict'],
  properties: {
    slug: { type: 'string' },
    machine_ratio: { type: 'number' },
    // NEEDS_SPLIT is in the enum because the scorer can now return it. Reported by
    // an agent during the first run of this pipeline, when the verdict existed in
    // SKILL.md's table and in no code — a brief needing a split had to be squeezed
    // into BLOCKED, which tells the reader to close gaps no rewrite can close.
    verdict: { type: 'string', enum: ['ALIGNED', 'AWAITING_REVIEW', 'BLOCKED', 'NEEDS_SPLIT'] },
    gaps: { type: 'array', items: { type: 'string' } },
  },
}

// NO `isolation: 'worktree'` on any stage, and the reason is two defects, not a
// preference. A worktree isolates the repository of the CWD — and the CWD here is
// whichever repo invoked the workflow, which for a consumer run is the KIT, not
// `REPO`. So the isolation guarded the wrong tree, and worse, it handed each agent
// a cwd inside the kit while its instruction named an absolute path in the
// consumer: a bare `git log` would have read this repository's history and been
// reported as the item's. The second defect is that it bought nothing anyway —
// all three generated stages are read-only (`tools: Read, Glob, Grep, Bash`, no
// Write, no Edit), and worktrees exist for agents that MUTATE files in parallel.
// Restore isolation when a writing stage lands, and give it the consumer's repo.

log(`pipeline over ${ITEMS.length} items · repo ${REPO}`)

// pipeline(), not parallel(): there is NO barrier between stages. Item B may be
// aligning while item C is still discovering, which is the entire shape being
// demonstrated — a barrier here would rebuild the sequential chain with extra
// machinery.
const results = await pipeline(
  ITEMS,

  // ── stage 1 · DISCOVER ────────────────────────────────────────────────────
  (item) => agent(
    stagePrompt(item, 'discover',
      `Run your stage now over ${item} in ${REPO}. Return the structured object.`),
    { label: `discover:${item}`, phase: 'Discover', schema: BRIEF },
  ),

  // ── stage 2 · ALIGN ───────────────────────────────────────────────────────
  (discovered, item) => agent(
    stagePrompt(item, 'align',
      `DISCOVER reported: ${JSON.stringify(discovered)}

` +
      `Run your stage now and return the structured object.`),
    { label: `align:${item}`, phase: 'Align', schema: SCORE },
  ),

  // ── stage 3 · JUDGE, the sign-off ALIGN is forbidden to give itself ───────
  //
  // This stage did not exist, and its absence was a gate that never closed.
  // `alignment-threshold.md` requires TWO independent things before an item may
  // be planned: a machine score at or above the threshold, AND a sign-off from a
  // reviewer who is not the brief's author. ALIGN can only ever produce the
  // first — its own template forbids it from emitting `ALIGNED` — so with no
  // stage for the second, every item arrived at PLAN unsigned by construction.
  //
  // Measured on a real backlog on 2026-09-02: five of seven items scored
  // `AWAITING_REVIEW` and ALL FIVE were sent to PLAN. Three of those five PLAN
  // agents refused the work on their own reading of the rule and two did not,
  // which is the gate holding only where an agent chose to hold it.
  (scored, item) => {
    if (!scored || scored.verdict !== 'AWAITING_REVIEW') {
      log(`  ${item} stops at ALIGN (${scored?.verdict ?? 'no score'}) — the line keeps moving`)
      return { slug: item, stage: 'parked', at: 'align',
               reason: scored?.gaps?.join('; ') ?? scored?.verdict ?? 'no score' }
    }
    return agent(
      stagePrompt(item, 'judge',
        `ALIGN reported: ${JSON.stringify(scored)}\n\n` +
        `Measure the score yourself, review the brief against the repository, ` +
        `and sign or refuse under your own name. Return the structured object.`),
      { label: `judge:${item}`, phase: 'Judge', schema: JUDGEMENT },
    ).then((judged) => ({ ...judged, slug: item }))
  },

  // ── stage 4 · PLAN, only for a brief that carries a signature ─────────────
  //
  // ALLOWLIST, and the distinction is the defect this replaces. The old test was
  // `verdict === 'BLOCKED'` — a denylist, which passes everything it was not
  // told to stop. Since ALIGN cannot emit `ALIGNED`, every reachable verdict fell
  // through it. `pipeline_orchestrator.py` had the correct shape all along
  // (`if verdict !== 'PASS'` → park, "the scheduler obeys the gate; it does not
  // reinterpret it"); this file duplicated that decision and drifted from it.
  (judged, item) => {
    const cleared = judged?.verdict === 'signed' && judged?.exit_code === 0
    if (!cleared) {
      if (judged?.stage === 'parked') return judged   // already stopped at ALIGN
      log(`  ${item} refused at the gate — ${judged?.reason ?? 'no judgement'}`)
      return { slug: item, stage: 'parked', at: 'judge',
               reason: judged?.gaps?.join('; ') ?? judged?.reason ?? 'no judgement' }
    }
    return agent(
      stagePrompt(item, 'plan',
        `The brief was signed by ${'`judge/alignment-judge`'} and the scorer exits 0. ` +
        `Run your stage now and return the structured object.`),
      { label: `plan:${item}`, phase: 'Plan', schema: OUTLINE },
    ).then((outline) => ({ ...outline, slug: item, stage: 'planned' }))
  },

  // ── stage 5 · IMPLEMENT, the first stage that writes ──────────────────────
  //
  // ALLOWLIST again, and the condition is narrow on purpose: tasks must exist.
  // An empty outline reaching a writing agent is an agent asked to improvise the
  // change, and improvised changes are what the alignment gate three stages back
  // exists to prevent.
  //
  // The TDD-shape gate is NOT applied here. `check_tdd_shape.py` is Python and
  // this file cannot run it, and a scheduler that approximated it would be a
  // second implementation of a rule that already has one — the defect this kit
  // found five times on 2026-09-02. IMPLEMENT runs the real gate as its first
  // action and halts on it, the same way JUDGE runs the real scorer.
  (planned, item) => {
    if (planned?.stage === 'parked') return planned
    const tasks = planned?.tasks ?? []
    if (!tasks.length) {
      log(`  ${item} planned nothing to implement — the line keeps moving`)
      return { ...planned, slug: item, stage: 'planned', implemented: false }
    }
    return agent(
      stagePrompt(item, 'implement',
        `PLAN produced ${tasks.length} task(s): ${JSON.stringify(tasks)}\n\n` +
        `Run the TDD-shape gate first and halt if it blocks. Otherwise make your ` +
        `worktree and work in it. Return the structured object.`),
      { label: `implement:${item}`, phase: 'Implement', schema: IMPLEMENTED },
    ).then((done) => ({ ...done, slug: item, stage: 'implemented' }))
  },
)

const parked = results.filter((r) => r?.stage === 'parked')
const planned = results.filter((r) => r?.stage === 'planned')
const implemented = results.filter((r) => r?.stage === 'implemented')
const partial = implemented.filter((r) => r.tasks_done < r.tasks_total)
log(`done · ${implemented.length} reached IMPLEMENT (${partial.length} partial) · ` +
    `${planned.length} stopped after PLAN · ${parked.length} parked at a gate`)

return {
  implemented: implemented.map((r) => ({ slug: r.slug, branch: r.branch,
                                         done: `${r.tasks_done}/${r.tasks_total}` })),
  planned: planned.map((p) => p.slug),
  parked: parked.map((p) => p.slug),
  results,
}
