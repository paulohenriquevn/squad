export const meta = {
  name: 'kit-self-audit',
  description: 'Hunt this kit for its own recurring defect patterns, then try to refute each finding',
  whenToUse: 'When the consumer queue is blocked and the fleet would otherwise idle, or after a batch of kit changes',
  phases: [
    { title: 'Hunt',   detail: 'one lens per known defect pattern, over the kit itself' },
    { title: 'Refute', detail: 'an independent agent tries to prove each finding wrong' },
  ],
}

// WHY A WORKFLOW AND NOT A GATE
//
// Every defect this kit found on 2026-09-02 was found by an agent doing OTHER
// work — running the pipeline over a consumer's backlog and noticing something
// wrong in the tooling underneath. Seven issues came in that way, all real. That
// is a good source and a slow one: it only finds what happens to be in the path.
//
// A gate cannot replace it either. These patterns are about MEANING — a guard
// that reads as protection and is not, a rule that lives in one file and is
// missing from another — and the kit already has 1180 assertions that see shape.
// The measured evidence for that gap: one brief scored 31/34 unchanged across
// five content defects and their fixes, and what caught them was a reviewer
// reading the repository.
//
// So this asks agents to look on purpose, at the patterns already known to
// recur, and then tries to prove each of them wrong before it is reported.

const REPO = args?.repo
if (!REPO) throw new Error('no repo: pass args.repo — the kit to audit')
const MAX = args?.maxPerLens ?? 4

// Each lens is a defect pattern this kit has shipped more than once, with the
// measurement that makes it concrete. The measurements are in the prompts on
// purpose: an agent told "look for silent failures" finds prose, and one told
// "a glob was renamed and the matcher reported a complete delta of 5 against a
// true 11" finds matchers.
const LENSES = [
  {
    key: 'absence-as-answer',
    prompt: `Find code in this kit that reports an ABSENCE as if it were an ANSWER.

Measured instances, all from one day:
- a syncer matched a directory renamed out from under it and printed "delta: 5
  files" when the true delta was 11, with "stale=0 local-change=0" reading clean
- a launcher created four tmux sessions stuck in a first-run dialog and printed
  that the fleet was watching them; a status tool showed them idle for 40 minutes
- \`git()\` returned "" for a missing binary, a timeout AND a broken repository,
  all indistinguishable from "nothing changed" — which is what made four
  end-of-session gates pass, one of them the secret check
- a gate printed "PASS — every cycle's declared numbering is unique" after
  examining zero cycles

Look for: a function whose failure path returns the same value as its
empty-success path; a matcher whose zero-match case is not reported; a report
whose wording asserts a universal over a set that may be empty.`,
  },
  {
    key: 'rule-in-one-file',
    prompt: `Find a RULE implemented in two places that could disagree.

Measured instances, five in one day: the self-mention filter on \`blocked_by\`
lived in the selector and not the gate (28 false blockers, every push refused);
the prose-outlives-the-edge rule lived in the gate and not the selector (an item
a person still owed a decision on, handed to the queue); the syncer's tree list
disagreed with the installer's; the drift report's cache list disagreed with the
installer's; two keyword lists answering "is this a bugfix" had drifted by one.

Look for: the same constant, regex, threshold or predicate written twice; two
scripts reading the same file with different parsers; a Python list restating a
shell array. Where duplication is DELIBERATE (a gate that must not import the
writer), the finding is the absence of a test holding them equal.`,
  },
  {
    key: 'guard-that-guards-nothing',
    prompt: `Find a guard that costs something and prevents nothing.

Measured: \`permissions.deny\` refused \`Read\` on 157 paths in one consumer — 79
of them source code — while \`Bash(*)\` was allowed, so \`cat\` returned the same
bytes and \`Edit\` was never denied at all. Also measured: a pipeline gate tested
\`verdict === 'BLOCKED'\` and advanced everything else, and since the stage before
it could not emit the only passing verdict, every reachable value fell through.

Look for: a deny list bound to one tool when several reach the same thing; a
check whose condition can never be true; a denylist where the set of things it
does not name is the set that matters; a threshold no code reads.`,
  },
  {
    key: 'mentioned-not-used',
    prompt: `Find something MENTIONED that is being counted as USED, or vice versa.

Measured: a brief that quoted the \`NEEDS_SPLIT\` marker while explaining it to a
reviewer was read as declaring one; a judge's signature containing the word
UNKNOWN made the placeholder criterion fail, so an APPROVING signature dropped a
brief from 34/34 to 32/34; a gate appeared in the repository exactly once outside
its tests — inside a comment — and that read as coverage.

Look for: a substring match where a structural match is meant; a name matched
anywhere in a file rather than at a call site; documentation counted as
implementation.`,
  },
  {
    key: 'prose-vs-mechanism',
    prompt: `Find prose that describes a world the code has left.

Measured on 2026-09-02: 3 of 4 stage templates promised each agent its own git
worktree, 1 line after the scheduler stopped creating one — one of them under a
heading reading "You are alone in this tree", by then the opposite of true. The
test that caught it had been written for the INVERSE case in 2026-08-30, when the
same templates told reviewers the tree was SHARED after isolation was added.

Look for: a docstring, SKILL.md, rule or template asserting behaviour the code
beside it no longer has. Check what the code DOES, not what its comment says it
does. Read the git history where it helps.`,
  },
  {
    key: 'unreachable-or-unrun',
    prompt: `Find a mechanism nothing executes, or a branch nothing reaches.

Measured on 2026-09-02: 2 of 18 gates were run by no CI job, no hook, no script
and not the ecosystem verifier — 1 of the 2 appeared outside its own tests
exactly once, inside a comment. Also measured: \`detect_domains.py\` carried a
"no derivable domain" message that 0 inputs could reach, so an empty directory
received a fabricated domain named after the folder, plus a routing table naming
1 specialist that would have to be written for it.

Look for: a script with no caller outside its tests; an error branch no input can
enter; a config key nothing reads; a verdict a rule declares that no code emits.`,
  },
]

const FINDING = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['title', 'file', 'evidence', 'why_it_matters'],
        properties: {
          title: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'integer' },
          evidence: { type: 'string' },
          why_it_matters: { type: 'string' },
          suggested_fix: { type: 'string' },
        },
      },
    },
  },
}

const VERDICT = {
  type: 'object',
  required: ['refuted', 'reason'],
  properties: {
    refuted: { type: 'boolean' },
    reason: { type: 'string' },
    // What the refuter ran or read. A verdict with no evidence is an opinion,
    // and this kit has spent a day removing opinions dressed as measurements.
    checked: { type: 'string' },
  },
}

log(`kit self-audit over ${REPO} · ${LENSES.length} lenses`)

// pipeline(), not parallel(): a lens that finishes first should have its findings
// refuted while the slower lenses are still hunting.
const results = await pipeline(
  LENSES,

  (lens) => agent(
    `You are auditing the Squad kit at ${REPO}. Read it; do not change it.\n\n` +
    `${lens.prompt}\n\n` +
    `Report at most ${MAX} findings, and report FEWER rather than padding — a ` +
    `finding you are unsure of costs a reviewer more than it saves. Every one ` +
    `needs a file, a line where you can give it, and evidence you actually ` +
    `gathered: a command you ran and its output, or the two places that ` +
    `disagree quoted side by side. "This looks fragile" is not a finding.\n\n` +
    `Do NOT report: style, naming, missing type hints, or anything the test ` +
    `suite already asserts — it holds 1180 assertions and they are not the gap. ` +
    `The gap is meaning.\n\n` +
    `Return the structured object. An empty list is a real answer and a common one.`,
    { label: `hunt:${lens.key}`, phase: 'Hunt', schema: FINDING },
  ),

  // Each finding meets an agent whose job is to kill it.
  (found, lens) => {
    const findings = found?.findings ?? []
    if (!findings.length) {
      log(`  ${lens.key}: nothing found`)
      return []
    }
    return parallel(findings.map((f) => () =>
      agent(
        `Try to REFUTE this claim about the Squad kit at ${REPO}.\n\n` +
        `Claim: ${f.title}\nFile: ${f.file}${f.line ? `:${f.line}` : ''}\n` +
        `Evidence offered: ${f.evidence}\nWhy it is said to matter: ${f.why_it_matters}\n\n` +
        `Go and check. Read the file, run the code, read the tests around it, read ` +
        `the git history if it decides the question. Refute it if the behaviour is ` +
        `deliberate and documented, if a test already covers it, if the claim ` +
        `misreads the code, or if the consequence described cannot actually occur.\n\n` +
        `Default to refuted=true when you cannot confirm it yourself. A finding ` +
        `that survives an honest attempt to kill it is worth a maintainer's time; ` +
        `one that survives only because nobody looked is worse than none.`,
        { label: `refute:${f.file.split('/').pop()}`, phase: 'Refute', schema: VERDICT },
      ).then((v) => ({ ...f, lens: lens.key, verdict: v }))))
  },
)

const all = results.flat().filter(Boolean)
const survived = all.filter((f) => f.verdict && !f.verdict.refuted)
log(`done · ${all.length} claim(s) hunted · ${survived.length} survived refutation`)
return { survived, refuted: all.length - survived.length, all }
