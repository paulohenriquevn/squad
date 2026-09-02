export const meta = {
  name: 'backlog-pipeline',
  description: 'Advance N backlog items through the cycle concurrently, one stage each',
  whenToUse: 'When a consumer has several triaged items waiting and the phases would otherwise sit idle between them',
  phases: [
    { title: 'Discover', detail: 'measure each item against the code, in its own worktree' },
    { title: 'Align',    detail: 'write and score an alignment brief per item' },
    { title: 'Plan',     detail: 'only for items whose brief cleared the gate' },
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
const ITEMS = args?.items ?? args?.queue
if (!Array.isArray(ITEMS) || ITEMS.length === 0) {
  throw new Error(
    'no queue: pass args.queue from `select_backlog_item.py --json`. ' +
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
    { label: `discover:${item}`, phase: 'Discover', schema: BRIEF, isolation: 'worktree' },
  ),

  // ── stage 2 · ALIGN ───────────────────────────────────────────────────────
  (discovered, item) => agent(
    stagePrompt(item, 'align',
      `DISCOVER reported: ${JSON.stringify(discovered)}

` +
      `Run your stage now and return the structured object.`),
    { label: `align:${item}`, phase: 'Align', schema: SCORE, isolation: 'worktree' },
  ),

  // ── stage 3 · PLAN, only for what cleared ─────────────────────────────────
  (scored, item) => {
    if (!scored || scored.verdict === 'BLOCKED') {
      log(`  ${item} parked at the gate (${scored?.machine_ratio ?? '?'}) — the line keeps moving`)
      return { slug: item, stage: 'parked', reason: scored?.gaps?.join('; ') ?? 'no score' }
    }
    return agent(
      stagePrompt(item, 'plan',
        `The brief cleared at ${scored.machine_ratio}. Run your stage now.`),
      { label: `plan:${item}`, phase: 'Plan', isolation: 'worktree' },
    ).then((text) => ({ slug: item, stage: 'planned', outline: text }))
  },
)

const parked = results.filter((r) => r?.stage === 'parked')
const planned = results.filter((r) => r?.stage === 'planned')
log(`done · ${planned.length} reached PLAN · ${parked.length} parked at the gate`)

return { planned: planned.map((p) => p.slug), parked: parked.map((p) => p.slug), results }
