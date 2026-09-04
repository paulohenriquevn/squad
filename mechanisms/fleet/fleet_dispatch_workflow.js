export const meta = {
  name: 'kit-fleet-dispatch',
  description: 'Fix one audited kit issue at a time, test-first, then verify the branch',
  whenToUse: 'When a kit issue needs to be addressed by a fleet lane running inside Claude Code',
  phases: [
    { title: 'Repair', detail: 'RED→GREEN: write a test that fails, then fix to make it pass' },
    { title: 'Verify', detail: 'independent agent checks the branch without writing' },
  ],
}

// WHY THIS EXISTS
//
// The fleet routes kit issues to interactive sessions. Each issue is a measured
// finding from the kit's own gates. This workflow receives the issue metadata,
// runs two phases (Repair + Verify), and reports the branch that fixes it or
// the reason repair refused.
//
// This replaces prose-based dispatch: the brief arrives as a structured JSON
// payload, not a markdown prose file. Structure reduces misinterpretation.
//
// WHY TWO PHASES
//
// Repair writes code. Verify checks it. They must be distinct agents because:
// - A test written after the fix passes on the fix that was written,
//   indistinguishable from one that verifies the requirement.
// - Two writers in one worktree produce a diff neither of them authored.
// - An unverified fix that reads as verified is worse than one nobody claimed to check.

const REPO = args?.repo
if (!REPO) throw new Error('no repo: pass args.repo — the kit repository path')

const UNIT = args?.unit
if (!UNIT || !UNIT.slug || UNIT.number === undefined) {
  throw new Error('no unit: pass args.unit with slug, number, title, body, branch')
}

const TRACKER = args?.tracker
if (!TRACKER) throw new Error('no tracker: pass args.tracker (github, jira, etc.)')

const WORKTREE_ROOT = args?.worktreeRoot ?? '/tmp/squad-dispatch'

// Schemas for structured output
const REPAIR = {
  type: 'object',
  required: ['slug', 'fixed', 'summary'],
  properties: {
    slug: { type: 'string' },
    fixed: { type: 'boolean' },
    branch: { type: 'string' },
    worktree: { type: 'string' },
    summary: { type: 'string' },
    red_evidence: { type: 'string' },
    green_evidence: { type: 'string' },
    files_touched: { type: 'array', items: { type: 'string' } },
    // Refusing is a real outcome: the issue may be wrongly diagnosed,
    // or the fix may be larger than one branch should carry.
    refused_because: { type: 'string' },
  },
}

const VERIFIED = {
  type: 'object',
  required: ['slug', 'holds', 'reason'],
  properties: {
    slug: { type: 'string' },
    holds: { type: 'boolean' },
    reason: { type: 'string' },
    // What the verifier RAN. A verdict with no command behind it is an opinion.
    checked: { type: 'string' },
  },
}

log(`dispatch kit-issue · unit ${UNIT.slug} (#${UNIT.number}) · repo ${REPO}`)

const results = await pipeline(
  [UNIT],

  // ── REPAIR ────────────────────────────────────────────────────────────────
  (unit) => agent(
    `Fix one audited kit issue. The issue survived validation and is ready to repair.\n\n` +
    `ISSUE: ${unit.title}\n` +
    `NUMBER: #${unit.number}\n` +
    `BODY:\n${unit.body}\n\n` +
    `## Where you work\n\n` +
    `Make your own worktree, and put every edit inside it:\n\n` +
    `    git -C ${REPO} worktree add -b ${unit.branch} ${WORKTREE_ROOT}/${unit.slug} HEAD\n\n` +
    `Other workflows may be repairing other issues in parallel. Two writers in one tree ` +
    `produce a diff neither authored.\n\n` +
    `## The test comes first\n\n` +
    `Write a test that FAILS against the current behaviour, run it, and record that it failed. ` +
    `Then fix. Then run it again. Report both runs — not claims about them. If the test passes ` +
    `before you change anything, the issue is misdiagnosed or you have not reproduced it; say which, ` +
    `and do not write a fix.\n\n` +
    `## Absolutes\n\n` +
    `No push. No commit outside your branch. No \`--no-verify\`, \`--force\`, or \`--allow-dirty-tree\`. ` +
    `Nothing outside your worktree.\n\n` +
    `## Before you finish\n\n` +
    `Run \`python3 -m pytest -q\` from your worktree. A fix that reddens the suite is not done. ` +
    `Commit on your branch with a message that names what was measured. Then return the structured object.\n\n` +
    `**Refusing is a real outcome.** If the issue misreads the code, or the fix is larger than ` +
    `one branch should carry, set fixed=false and say why.`,
    { label: `repair:${unit.slug}`, phase: 'Repair', schema: REPAIR },
  ).then((r) => ({ ...r, slug: unit.slug, unit })),

  // ── VERIFY, by an agent that did not write it ─────────────────────────────
  (repair, unit) => {
    if (!repair?.fixed) {
      log(`  ${unit.slug}: not fixed — ${repair?.refused_because ?? 'no result'}`)
      return { ...repair, slug: unit.slug, verified: null }
    }
    return agent(
      `Check a repair somebody else made in the kit repository at ${REPO}.\n\n` +
      `ISSUE IT CLAIMS TO FIX: ${unit.title}\n` +
      `BRANCH: ${repair.branch}\n` +
      `WORKTREE: ${repair.worktree}\n` +
      `WHAT THEY SAY THEY DID: ${repair.summary}\n` +
      `RED THEY REPORT: ${repair.red_evidence ?? '(none reported)'}\n` +
      `GREEN THEY REPORT: ${repair.green_evidence ?? '(none reported)'}\n\n` +
      `Read the diff (\`git -C ${REPO} diff HEAD...${repair.branch}\`). Then check, ` +
      `by running things rather than by reading:\n\n` +
      `1. Does the new test actually FAIL without the fix? Revert the production ` +
      `   change in a scratch copy and watch it. A test that passes either way ` +
      `   proves nothing.\n` +
      `2. Does the suite pass on that branch?\n` +
      `3. Did they change a threshold, a baseline, or an allowlist to get there? ` +
      `   That is not a fix.\n` +
      `4. Does the fix address the issue, or something adjacent that was easier?\n\n` +
      `Say holds=false if any check fails or you cannot run it. "I could not verify" ` +
      `is holds=false, not holds=true.`,
      { label: `verify:${unit.slug}`, phase: 'Verify', schema: VERIFIED },
    ).then((v) => ({ ...repair, slug: unit.slug, verified: v }))
  },
)

const all = results.flat().filter(Boolean)
const held = all.filter((r) => r.verified && r.verified.holds)
const rejected = all.filter((r) => r.fixed && r.verified && !r.verified.holds)
const refused = all.filter((r) => !r.fixed)

log(`done · ${held.length} verified · ${rejected.length} rejected by the verifier · ` +
    `${refused.length} refused by the repairer`)

return {
  held: held.map((r) => ({ slug: r.slug, branch: r.branch, summary: r.summary })),
  rejected: rejected.map((r) => ({ slug: r.slug, why: r.verified.reason })),
  refused: refused.map((r) => ({ slug: r.slug, why: r.refused_because })),
  all,
}
