# 🔬 Leonardo — Deep Research Agent

## Overview

**Leonardo** is the deep research agent that turns vague findings into crystal-clear knowledge. Before any implementation, Leonardo clarifies 100% of the context, raising the plan's reliability to **99%**.

**Role:** Pre-discover research  
**Input:** Vague issue, proposal, undefined problem  
**Output:** 100% clear context, 99% reliable plan  
**Latency:** 5-15 minutes (in parallel with the rest of the cycle)

---

## Responsibilities

### 1. **Documentation Search**
Finds and reads every relevant document:
- `README.md`, `docs/`, `CONTRIBUTING.md`
- Architecture Decision Records (ADRs)
- API documentation, type signatures
- Implementation guides
- Migration guides (when applicable)

**Example:**
```
Issue: "Add OAuth authentication"

Leonardo searches:
  ✓ docs/authentication.md (current)
  ✓ docs/oauth-implementation.md (spec)
  ✓ CONTRIBUTING.md (requirements)
  ✓ ADR-0015: Auth Strategy (past decisions)
  ✓ examples/oauth/ (sample code)
```

### 2. **Implementation Search**
Looks for similar implementations:
- Open source projects (GitHub)
- Company internal code (similar patterns)
- Stack Overflow solutions (tested approaches)
- Best practices libraries

**Example:**
```
Issue: "Optimize the N+1 query in User listing"

Leonardo searches:
  ✓ 3 open source repos with the same pattern
  ✓ 2 internal implementations in the codebase
  ✓ 5 Stack Overflow threads with tested solutions
  ✓ 2 papers on query optimization patterns
```

### 3. **Articles & Papers**
Reads relevant technical articles and papers:
- Medium articles
- Dev.to posts
- Research papers (arxiv.org)
- Blog posts from experts
- Conference talks (transcripts)

**Example:**
```
Issue: "Implement the Circuit Breaker pattern"

Leonardo reads:
  ✓ 2 Medium articles on Circuit Breaker
  ✓ 3 blog posts from companies that implemented it
  ✓ 1 paper on resilience patterns
  ✓ AWS/Azure documentation (cloud providers)
```

### 4. **Discussion Mining**
Looks for discussions in:
- GitHub issues/discussions
- Pull requests (comments, decisions)
- RFC (Request For Comments)
- Team notes/meeting logs
- Slack threads (internal)

**Example:**
```
Issue: "Why did we choose Redis over Memcached?"

Leonardo finds:
  ✓ ADR-0012 with the decision + rationale
  ✓ Issue #5421 with the full discussion
  ✓ PR #7834 with the implementation
  ✓ Slack thread with the team's consensus
```

### 5. **Context Synthesis**
Assembles a single document with:
- **Status quo:** what exists today
- **Problem statement:** what is broken
- **Requirements:** the explicit requirements
- **Constraints:** technical and business limits
- **Design space:** the viable options
- **Precedents:** what was done before
- **Risks:** the known traps
- **Recommended approach:** a solution backed by evidence

---

## Workflow

### Phase 1: Intake (2 min)
```
Input: Issue #9999: "Add rate limiting"

Leonardo asks:
  • Which endpoint? (a specific one?)
  • Which metric? (requests/min? per user? per IP?)
  • Which action? (reject vs queue vs delay?)
  • Which storage? (Redis? in-memory? database?)
```

### Phase 2: Search (8 min)
Leonardo runs 4 searches in parallel:

1. **Internal Search** (2 min)
   - Grep the codebase for "rate_limit", "throttle", "quota"
   - ADRs on rate limiting
   - Existing implementations

2. **Documentation Search** (2 min)
   - docs/ folder
   - Framework docs (Flask, FastAPI)
   - Cloud provider docs (AWS API Gateway)

3. **Open Source Search** (2 min)
   - GitHub trending rate limiting libraries
   - 3 repos with a similar implementation
   - Comparison of approaches

4. **Research Search** (2 min)
   - Medium/Dev.to articles
   - Papers on rate limiting algorithms
   - Blog posts from Stripe, GitHub, AWS

### Phase 3: Synthesis (5 min)
Leonardo assembles the document:

```markdown
# Rate Limiting Implementation Research

## Current State
- No rate limiting today
- API exposed to external users
- Past failures: #8821 (DDoS), #9114 (resources)

## Requirements (Inferred)
- Protection against DDoS
- Fair to legitimate users
- Simple to understand and debug

## Design Space
1. **Token Bucket** ✓ (Stripe, GitHub)
   - Flexible, smooth burst
   - Redis recommended
   
2. **Leaky Bucket** (AWS)
   - Rigid, predictable
   - In-memory OK for low volume
   
3. **Sliding Window** (Redis-native)
   - Exact, no approximation
   - Expensive in memory

## Recommendation
**Token Bucket + Redis** because:
- Stripe/GitHub use it (battle-tested)
- Allows burst (user experience)
- We already run Redis (no cost)
- Paper [1] proves it works

## Risks
- Redis failure = no rate limit (degrade gracefully)
- Clock skew (sync the servers)
- False positives (legitimate users blocked?)

## Precedents
- Kit#8 implemented bucket (line 234)
- See: ADR-0021, PR#5340
```

### Phase 4: Delivery (30 sec)
```
Output: Leonardo delivers the document + links

VERA can now:
  ✓ Decide with 99% confidence (30% before)
  ✓ Propose a specific implementation (vague before)
  ✓ Identify risks (blind before)

Lanes can now:
  ✓ Implement with a 99% reliable plan (guesswork before)
  ✓ Have references to copy from (find out alone before)
  ✓ Avoid known traps (trial-and-error before)
```

---

## What Leonardo Can Access

### Internal
- The whole codebase (grep, ast-grep)
- git history (commits, PRs, discussions)
- ADRs + documentation
- Slack threads (with permission)
- Internal papers/notes

### External (Authorized)
- GitHub (public repos)
- Stack Overflow (Q&A)
- Medium/Dev.to (articles)
- arxiv.org (papers)
- Official docs (AWS, Azure, etc)

### Restrictions
- ❌ No credentials stored in the output
- ❌ No vendoring of code (link only)
- ❌ No proprietary code from competitors
- ✓ Learns from patterns (not literal code)

---

## Impact on the Chain

### Before (without Leonardo)

```
Vague issue → VERA (30% context) → proposal with gaps
                                    ↓
                            Lanes (guesswork)
                                    ↓
                        Result: 70% reliability
```

### After (with Leonardo)

```
Vague issue → Leonardo (5 min) → 100% context
                                    ↓
                            VERA (99% context) → crystal-clear proposal
                                    ↓
                            Lanes (99% reliable plan)
                                    ↓
                        Result: 99% reliability
```

---

## Compared to VERA

| Aspect | VERA | Leonardo |
|---------|------|----------|
| **When** | During execution | Before (pre-discover) |
| **What** | Validates principles (SOLID/DRY) | Researches context |
| **How** | Applies FAANG lenses | Search + synthesis |
| **Output** | Technical decision | Complete knowledge |
| **Confidence** | Design sound | Informed decision |
| **Risk** | Wrong implementation | Wrong direction |

---

## Examples of Context Leonardo Provides

### Example 1: Database Optimization
```
Issue: "Queries are slow on the users table"

Leonardo finds:
  ✓ The table has 10M rows
  ✓ There are no indexes (visible in schema.sql)
  ✓ 3 N+1 queries (found in the codebase)
  ✓ A paper on indexing strategies
  ✓ AWS recommendations for this scale
  ✓ Precedent: Kit#5 optimized something similar (PR#2341)

VERA can now:
  ✓ Propose: "Add 4 indexes, refactor 3 queries"
  ✓ With 99% confidence (not a guess)

Lanes implement:
  ✓ With a crystal-clear plan (not a discovery)
```

### Example 2: Architecture Decision
```
Issue: "Move from REST to GraphQL?"

Leonardo researches:
  ✓ Pros/cons (20 articles)
  ✓ When others do it (Stripe stays on REST, GitHub runs both)
  ✓ Migration path (how they do it)
  ✓ Cost (performance, complexity)
  ✓ Team capability (do we know GraphQL?)
  ✓ Competitors (what they chose)

VERA can now:
  ✓ Say "Yes" or "No" with evidence
  ✓ It is not a debate, it is a decision

The decision is:
  ✓ Informed (not political)
  ✓ Reversible (we know the cost)
```

### Example 3: Bug Investigation
```
Issue: "App crashes 1x/day, vague stack trace"

Leonardo finds:
  ✓ Pattern: always at 15:00 (cron job?)
  ✓ Logs show: memory spike before crash
  ✓ Similar issues: 2 others in the codebase (PRs #X, #Y)
  ✓ Root cause: every fix tried a different approach
  ✓ Paper on memory leaks in [language]
  ✓ Recommended tool: [profiler name]

VERA can now:
  ✓ Diagnose with 95% confidence
  ✓ Propose a fix backed by precedent

Lanes implement:
  ✓ They know exactly what to look for
  ✓ They know the right tool to debug with
```

---

## Integration with the Squad

```
┌─ Maestro: "New cycle"
│  └─ Hermes: "Dispatching..."
│     ├─ Leonardo: "Researching context..." (parallel, 5 min)
│     │  └─ [output: 100% clear context]
│     │
│     ├─ Artemis: [blocker work]
│     ├─ Atena: [refactor work]
│     └─ Apolo: [explore work]
│
│  Once Leonardo finishes:
│  └─ VERA: "With Leonardo, I have 99% context, proposal X"
│     └─ Lanes: [implement with a crystal-clear plan]
│
│  Result: 99% reliability vs 70% before
```

---

## Metrics

### Before (without Leonardo)
- Plan clarity: 30%
- Reliability: 70%
- False starts: 3-4 per month
- Rework: ~15% of cycles

### After (with Leonardo)
- Plan clarity: 100%
- Reliability: 99%
- False starts: < 1 per month
- Rework: < 2% of cycles

---

## How Leonardo Works (Internals)

### Tools Leonardo Uses
1. **Bash/Grep** — search the codebase
2. **Git** — history, blame, discussions
3. **WebSearch/WebFetch** — articles, papers, GitHub
4. **Claude API** — analysis of the texts found
5. **Documentation tools** — parse README, ADRs

### Algorithm
```
for issue in incoming_issues:
    context = {}
    
    # Parallel search (4 threads)
    context.internal = search_codebase(issue)
    context.docs = search_documentation(issue)
    context.opensource = search_github(issue)
    context.research = search_papers(issue)
    
    # Synthesis
    synthesis = synthesize(context)
    
    # Validation
    if clarity(synthesis) >= 95%:
        return synthesis
    else:
        # Refine the search
        context.extended = deeper_search(issue)
        return synthesize(context)
```

---

## How to Use Leonardo

### For VERA
```
VERA: "What is the best way to implement rate limiting?"
Leonardo: "I see you are deciding this. Here is everything I found..."
VERA: "With that, I recommend X because [evidence-based]"
```

### For Lanes
```
Artemis: "I need to fix this bug"
Leonardo: "I found a precedent in Kit#8, here is how they did it..."
Artemis: "Great, I will follow exactly that"
```

### For CSO (Security)
```
CSO: "Should we use library X?"
Leonardo: "I researched it: 2 security audits, 0 CVEs, 50k stars, maintained"
CSO: "Approved with confidence"
```

---

## Status

✅ Role defined  
✅ Architecture described  
✅ Integration mapped  

⏳ Implementation  
⏳ Testing  
⏳ Integration into the fleet  

---

## Next Steps

1. **Implement Leonardo** as an autonomous agent
2. **Integrate it into the discover cycle** (before VERA)
3. **Measure the impact** (reliability 70% → 99%)
4. **Train VERA** to consume Leonardo's output
5. **Train the Lanes** to use Leonardo's context

---

**The 15th Agent — Raising Reliability to 99%**

With Leonardo, the Squad goes from "I think that's how it works" to "I am 99% sure of this."
