export const meta = {
  name: 'kit-parallel-repair',
  description: 'Fix N audited findings at once, one worktree each, test-first, then verify every branch',
  whenToUse: 'After kit-self-audit produces findings that survived refutation, and their files are disjoint',
  phases: [
    { title: 'Repair', detail: 'one agent per finding, in its own worktree of the kit' },
    { title: 'Verify', detail: 'an agent that did not write the fix checks the branch' },
  ],
}

// WHY THIS EXISTS
//
// The self-audit produced 17 findings and 16 survived refutation. They were then
// fixed ONE AT A TIME, by hand, over several hours — and the files they touch are
// disjoint, so nothing about the work required that order. Measured on the day:
// four fixes took roughly an hour each in sequence while three lanes of a fleet
// sat idle.
//
// This is the IMPLEMENT stage's shape applied to the kit itself: a worktree per
// item, RED before GREEN, no push, and a second agent that did not write the fix
// deciding whether it holds.
//
// WHY A WORKTREE PER FINDING, AND NOT JUST PARALLEL AGENTS
//
// Two writers in one tree produce a diff neither authored. The findings' target
// files are disjoint, but their TESTS need not be, and `git status` is shared
// whatever the file list says. A worktree is cheap next to a wrong diff nobody
// can attribute.

const KIT = args?.kit
if (!KIT) throw new Error('no kit: pass args.kit — the repository to repair')
const FINDINGS = args?.findings
if (!Array.isArray(FINDINGS) || !FINDINGS.length) {
  throw new Error('no findings: pass args.findings from the self-audit')
}
const WORKTREES = args?.worktreeRoot ?? '/tmp/squad-repair'

const slug = (f, i) =>
  `${String(i + 1).padStart(2, '0')}-${(f.file || 'x').split('/').pop().replace(/[^a-z0-9]+/gi, '-')}`
    .toLowerCase().slice(0, 48)

const REPAIR = {
  type: 'object',
  required: ['slug', 'fixed', 'summary'],
  properties: {
    slug: { type: 'string' },
    fixed: { type: 'boolean' },
    branch: { type: 'string' },
    worktree: { type: 'string' },
    summary: { type: 'string' },
    // Both runs. A test written after the fix passes on the fix you happened to
    // write, and cannot be told apart from one that verifies the requirement.
    red_evidence: { type: 'string' },
    green_evidence: { type: 'string' },
    files_touched: { type: 'array', items: { type: 'string' } },
    // Refusing is a real outcome: the finding may be wrong, or the fix may be
    // larger than one branch should carry.
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

log(`parallel repair · ${FINDINGS.length} finding(s) · kit ${KIT}`)

const results = await pipeline(
  FINDINGS.map((f, i) => ({ ...f, slug: slug(f, i) })),

  // ── REPAIR ────────────────────────────────────────────────────────────────
  (f) => agent(
    `Fix one audited finding in the Squad kit at ${KIT}. It survived an ` +
    `independent attempt to refute it, so treat it as real until your own ` +
    `reading says otherwise.\n\n` +
    `FINDING: ${f.title}\n` +
    `FILE: ${f.file}${f.line ? `:${f.line}` : ''}\n` +
    `EVIDENCE: ${f.evidence}\n` +
    `WHY IT MATTERS: ${f.why_it_matters}\n` +
    (f.suggested_fix ? `SUGGESTED FIX: ${f.suggested_fix}\n` : '') +
    `\n## Where you work\n\n` +
    `Make your own worktree first, and put every edit inside it:\n\n` +
    `    git -C ${KIT} worktree add -b repair/${f.slug} ${WORKTREES}/${f.slug} HEAD\n\n` +
    `Other agents are repairing other findings in this same repository right ` +
    `now. Two writers in one tree produce a diff neither of them authored.\n\n` +
    `## The test comes first\n\n` +
    `Write a test that FAILS against the current behaviour, run it, and record ` +
    `that it failed. Then fix. Then run it again. Report both runs — not a claim ` +
    `about them. If the test passes before you change anything, the finding is ` +
    `wrong or you have not reproduced it; say which, and do not write a fix.\n\n` +
    `## Absolutes\n\n` +
    `No push. No commit outside your branch. No \`--no-verify\`, \`--force\`, or ` +
    `\`--allow-dirty-tree\`. No moving a threshold, a baseline or an allowlist to ` +
    `make something pass — changing the measure to fit the result is the failure ` +
    `this kit is built against. Nothing outside your worktree.\n\n` +
    `## Before you finish\n\n` +
    `Run \`python3 -m pytest -q\` from your worktree. A fix that reddens the ` +
    `suite is not done. If it reddens something unrelated to your change, say so ` +
    `rather than fixing it here — that is a second finding, not part of this one.\n\n` +
    `Commit on your branch with a message that names what was measured. Then ` +
    `return the structured object.\n\n` +
    `**Refusing is a real outcome.** If the finding misreads the code, or the fix ` +
    `is larger than one branch should carry, set fixed=false and say why. A wrong ` +
    `fix costs more than an unfixed finding, because the next reader trusts it.`,
    { label: `repair:${f.slug}`, phase: 'Repair', schema: REPAIR },
  ).then((r) => ({ ...r, slug: f.slug, finding: f })),

  // ── VERIFY, by an agent that did not write it ─────────────────────────────
  (repair, f) => {
    if (!repair?.fixed) {
      log(`  ${f.slug}: not fixed — ${repair?.refused_because ?? 'no result'}`)
      return { ...repair, slug: f.slug, verified: null }
    }
    return agent(
      `Check a repair somebody else made in the Squad kit at ${KIT}.\n\n` +
      `FINDING IT CLAIMS TO FIX: ${f.title}\n` +
      `BRANCH: ${repair.branch}\nWORKTREE: ${repair.worktree}\n` +
      `WHAT THEY SAY THEY DID: ${repair.summary}\n` +
      `RED THEY REPORT: ${repair.red_evidence ?? '(none reported)'}\n` +
      `GREEN THEY REPORT: ${repair.green_evidence ?? '(none reported)'}\n\n` +
      `Read the diff (\`git -C ${KIT} diff HEAD...${repair.branch}\`). Then check, ` +
      `by running things rather than by reading the report:\n\n` +
      `1. Does the new test actually FAIL without the fix? Revert the production ` +
      `   change in a scratch copy and watch it. A test that passes either way ` +
      `   proves nothing and is the most common way a fix looks done.\n` +
      `2. Does the suite pass on that branch?\n` +
      `3. Did they change a threshold, a baseline, an allowlist, or the test's own ` +
      `   expectation to get there? That is not a fix.\n` +
      `4. Does the fix address the finding, or something adjacent that was easier?\n\n` +
      `Say holds=false if any check fails or you cannot run it. "I could not ` +
      `verify" is holds=false, not holds=true — an unverified fix that reads as ` +
      `verified is worse than one nobody claimed to check.`,
      { label: `verify:${f.slug}`, phase: 'Verify', schema: VERIFIED },
    ).then((v) => ({ ...repair, slug: f.slug, verified: v }))
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
