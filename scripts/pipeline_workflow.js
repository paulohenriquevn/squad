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
const ITEMS = args?.items ?? ['B-001', 'B-022', 'B-033']
const REPO = args?.repo ?? '/home/paulo/Projetos/theo/theo-platform/theo'
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
    verdict: { type: 'string', enum: ['ALIGNED', 'AWAITING_REVIEW', 'BLOCKED'] },
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
