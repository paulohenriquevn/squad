# ADR-0025: Organizational Hierarchy with Autonomous Squad

**Status:** Superseded by [`rules/autonomy-envelope.md`](../../rules/autonomy-envelope.md) and [`rules/squad-map.md`](../../rules/squad-map.md) (2026-09-08)

> **What superseded it.** This ADR describes a hierarchy of PEOPLE around the system —
> CTO, managers, architects — and states that Squad's fourteen agents handle "100% of
> technical execution". The kit does not implement an organisation chart, and the two
> questions this ADR actually answers are now answered by mechanisms rather than by an
> org structure:
>
> - *what does the system decide, and what stays with a person?* →
>   `rules/autonomy-envelope.md`, whose five floors and retained decision classes are
>   read by `halt_disposition.py`;
> - *who are the fourteen, and what does each one decide?* → `rules/squad-map.md`,
>   verified against `agents/` by `check_squad_map.py`.
>
> It is kept because an ADR records a decision that was taken, and deleting one hides
> that it ever was. It is not a description of the running system.
**Date:** 2026-09-03  
**Context:** Building out Theo as a complete software development organization with human leadership and fully autonomous AI execution infrastructure.

---

## Problem

Theo required a clear organizational structure that:
1. **Defines human roles and decision authority** — CTO, Managers, Architects, Product Owner, Engineers, QA
2. **Describes how Squad (the AI system) fits** — 14 autonomous agents handling 100% of technical execution
3. **Specifies decision boundaries** — what Squad decides vs what humans decide
4. **Enables scaling** — from 1 kit to 5+ kits without adding human bottlenecks
5. **Maintains accountability** — humans stay in control of strategy, Squad handles tactics

---

## Solution

Implement a **three-layer organizational structure** inspired by AIDLC Workflows:

### Layer 1: Executive (CTO)
- **Responsibility:** Strategic vision, quarterly backlog approval, risk escalation
- **Decision authority:** What work category is approved? What technologies to adopt? Risk tolerance?
- **Intervention frequency:** 1-2 times per month (strategic only)
- **How it works:** CTO approves backlog once per quarter; Squad routes all approved work autonomously

### Layer 2: Management (3 Managers)
- **Responsibility:** People allocation, pairing, capacity planning, delivery sequencing
- **Decision authority:** Who pairs with whom? Team composition? Delivery timeline?
- **Intervention frequency:** 1-2 times per week (team health, capacity planning)
- **How it works:** Managers monitor Squad logs; ensure team health and sustainable pace

### Layer 3: Specialists (4 Architects + 1 CSO)
All report directly to CTO (equivalent decision authority)

**Architects (4):**
- **Systems Architect:** Infrastructure, scaling, SLO, tradeoffs
- **Domain Architect:** Core kits, module structure, contracts
- **Security Architect (NEW):** Threat modeling, policies, compliance, incident strategy
- **Product Owner:** Backlog prioritization, user requirements

**Chief Security Officer (NEW):**
- Reports directly to CTO (equivalent level to Architects)
- **Responsibility:** Threat modeling execution, security policy definition, incident response, compliance
- **Decision authority:** Threat models, security policies, incident disclosure, vendor assessment
- **Intervention frequency:** Strategic approvals (quarterly); incident response (as-needed)

### Layer 4: Execution (Developers, QA, SRE, Security Engineer)
All report to respective Architects (technical guidance) and Managers (capacity/people)

- **Developers (3-5):** Pair with lanes, clarify requirements, code quality
- **QA Engineer (1):** Test strategy audit, test quality validation, CX testing
- **SRE / DevOps (1):** Observability, alerting, on-call, incident support
- **Security Engineer (1):** Reports to Security Architect
  - SAST, secret scanning, dependency audit
  - First responder for security incidents
  - Forensics and RCA
  - On-call 24/7 for critical incidents

**Decision authority:** "Is this clear?" "Are metrics healthy?" "Do tests protect?" "Is this secure?"  
**Intervention frequency:** Continuous monitoring; all blocking decisions flow through automated validation first

### Squad: 14 Autonomous Agents (100% Technical Execution)

Squad runs continuously, 100% autonomously, never requiring human approval for technical decisions:

**Execution (3 Lanes)**
- 3 parallel branches (`fix/kitN`)
- Each lane receives unit of work and generates code autonomously
- All commits pushed to origin; lander validates before integrating

**Routing (Fleet Router)**
- Reads work from 3 sources (in priority): Consumer Backlog (approved by PO) → Kit Issues (discovered by sweep) → VERA Proposals (IA-decided)
- Intelligent dedup: never offers same work twice
- Intelligent guard: never offers work in-flight
- Load balancing: lanes are never starved

**Integration (Fleet Lander)**
- Tests branch in isolation (suite A)
- Tests merge in scratch tree (suite B)
- Refuses with explicit reason or pushes to workspace
- Validates cleanup (no leaked worktrees)
- Handles multiple branches per pass

**Descoberta (VERA + Sweep)**
- **VERA:** Applies 6 FAANG lenses (SOLID, DRY, Coupling, Fail-Fast, Clarity, **SECURITY**) to 14 open problems; proposes objective solutions
- **Sweep:** Runs 7 defect-pattern lenses on diffs before landing; transforms findings into GitHub issues
  - Includes: guard-that-guards-nothing, absence-as-answer, fetch-stale-snapshot, workstation-path-leak, second-copy-of-rule, cleanup-discarded, **secret-in-plaintext**
- Both are informational; do not block landing

**Security Layer**
- **Chief Security Officer (CSO):** Reports to CTO; defines threat models, security policies, incident response
- **Security Engineer:** Operationalizes security via SAST, secret scanning, dependency scanning, incident response
- **VERA SECURITY lense:** Detects SQL injection, command injection, auth bypass, weak crypto, plaintext secrets, unsafe deserialization
- **Sweep SECRETS lense:** Detects credentials, API keys, private keys, database passwords, crypto keys in plaintext
- **Lander validation:** Runs SAST + secret scanning + dependency audit; rejects landing if high-severity findings

---

## Decision Boundaries

### Squad Decides (Autonomous)
✅ How to refactor a module (VERA applies SOLID)  
✅ Which bug to fix first (Router prioritizes by tag)  
✅ When to test (Lander runs 2 suites automatically)  
✅ When to integrate (Lander pushes when verified)  
✅ When to propose new work (VERA discovers via lenses)  
✅ How to name variables, structure files (Lane generation + test validation)  

**Humans never interfere** — system is 5/5 autonomous.

### Humans Decide (CTO + Product Owner)
✅ Should we start *new* kit? (CTO — quarterly)  
✅ Is this feature in scope for next quarter? (PO — quarterly)  
✅ Should we accept 30 days of tech debt for deadline? (CTO — rare escalation)  
✅ Should we discontinue a kit? (CTO — strategic)  

**Humans decide quarterly or strategically** — minimal interruption.

### Humans Monitor (Managers + SRE)
👀 Are we going too fast? (Manager — code review post-landing)  
👀 Is tech debt growing? (CTO — monthly metric review)  
👀 Are metrics healthy? (SRE — continuous)  
👀 Do tests protect behavior? (QA — weekly spot check)  

**Monitoring is continuous; blocking decisions are rare.**

---

## Feedback Loops

Every iteration closes a feedback loop (20–40 minutes per cycle):

```
[Router] → [Lanes] → [Lander] → [Propagation] → [Feedback] → [Router]
  ↓          ↓         ↓            ↓              ↓           ↑
Issue    Code Gen   Validate   Kit Updated    SRE/QA      Back to top
found    + Commit   2 Suites   + Consumer     observes    (continuous)
                    + Push     propagates     + Sweep
```

- **Discovery:** Sweep finds defects, VERA proposes solutions
- **Work Generation:** Router converts issues/proposals into units for lanes
- **Execution:** Lane 1/2/3 work in parallel; push to origin
- **Validation:** Lander runs 2 suites; accepts or rejects with reason
- **Propagation:** Workspace updated; Kit updated; Consumer updated
- **Feedback:** SRE sees metrics; QA runs manual CX tests; Sweep runs again
- **Next iteration:** Feedback becomes new issues → back to Router

No human is in this loop. It runs continuously, 24/7 if necessary.

---

## Scaling Model

### Today: 1 Kit
- 3 lanes (parallel)
- 1 lander (sequential, not bottleneck)
- 1 VERA + Sweep (shared)

### Future: 5 Kits
- **Fleet 1:** 3 lanes (Kit#1, Kit#2)
- **Fleet 2:** 3 lanes (Kit#3, Kit#4)
- **Fleet 3:** 3 lanes (Kit#5)
- **Central Lander:** Coordinates integrals across all fleets (with workspace lock)
- **Central VERA:** Runs across all fleets (or per-fleet VERA)

No increase in human coordination required. Each fleet is independent; only lander is centralized (not a bottleneck: 40 min per 3 branches).

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Squad proposes bad refactor | VERA applies 5 FAANG lenses; tests validate; code review post-landing |
| Lander pushes broken code | 2 suites (branch + merge); Cleanup validated; no silent failures |
| Lanes starve (not given work) | Router load-balances; reaper cleans abandoned units |
| Tech debt accumulates | Sweep + VERA continuously discover; tracked as GitHub issues; CTO reviews quarterly |
| Critical bug blocks fleet | `blocker` tag deprioritizes other work; Squad turnaround < 60 min |
| New technology introduced without approval | CTO quarterly backlog approval includes "technologies to adopt/retire" |
| Human reviewer has outdated info | Code review happens post-landing (never blocks); git history + logs are source of truth |

---

## Comparison to AIDLC Workflows

AIDLC uses **14 human agents** (Product, Design, Delivery, Architect, AWS Platform, Compliance, DevSecOps, Developer, Quality, Pipeline, Operations) that are AI-assisted personas.

Theo uses **14 AI agents** (Lane 1/2/3, Router, Lander, VERA, Sweep, and supporting utilities) orchestrated by **8 human roles** (CTO, 3 Managers, 2 Architects, Product Owner, QA, SRE).

**Key difference:** AIDLC is human-led (AI helps); Theo is AI-led (humans govern).

---

## Metrics

| Metric | Target | Owner | Frequency |
|--------|--------|-------|-----------|
| Cycle time (issue → shipped) | < 40 min | Squad logs | Continuous |
| Landing success (branches pass) | > 90% | Fleet Lander | Every landing |
| Blocker turnaround | < 60 min | Squad logs | Every blocker |
| Test coverage | > 75% | QA + pytest | Weekly |
| Tech debt ratio | < 10% | Sweep + CTO | Monthly |
| VERA adoption (proposals → code) | > 80% | Git logs | Quarterly |
| **Security findings (SAST)** | **0 high/critical** | **Lander + CSO** | **Every landing** |
| **Secret leaks detected** | **0** | **Sweep + Security Eng** | **Continuous** |
| **Vulnerable dependencies** | **0 high/critical** | **Lander + CSO** | **Every landing** |
| **Threat model coverage** | **100%** | **CSO + VERA** | **Quarterly** |
| **Incident MTTR (respond)** | **< 15 min** | **Security Eng** | **On-incident** |
| **Incident MTTR (recover)** | **< 60 min** | **Security Eng + Lane** | **On-incident** |

---

## Alternatives Considered

### 1. Fully Automated (No Humans)
❌ **Rejected:** Requires human accountability for strategic direction, budgets, market timing, regulatory compliance.

### 2. Fully Manual (No Squad)
❌ **Rejected:** Humans become bottleneck; cycle time 10+ days; scalability limited to 2-3 people.

### 3. Hybrid (Humans Approve Every Change)
❌ **Rejected:** Squad would require human sign-off for every technical decision, destroying autonomy. Cycle time would return to hours/days.

### 4. Chosen: Humans Govern, Squad Executes
✅ **Selected:** Maintains human control of strategy (backlog, direction, risk) while Squad handles 100% of technical execution. Autonomy + Accountability.

---

## Implementation Checklist

- [x] Fleet Router (intelligent dispatch, dedup, reaper)
- [x] Fleet Lander (2-suite validation, cleanup reporting)
- [x] VERA (5 FAANG lenses, GitHub issue generation)
- [x] Sweep (6 defect patterns, automated discovery)
- [x] Lane supervision (heartbeat, session ready)
- [x] Squad Lead (orchestration, logging)
- [x] 1348+ tests passing
- [x] Documentation (SQUAD_AGENTS.md, this ADR)
- [ ] Dashboard (real-time cycle visualization)
- [ ] Slack integration (alerts, metrics)
- [ ] Scaling to 5 kits (design ready, implementation future)

---

## Consequences

### Positive
- ✅ Cycle time: issue → shipped in < 40 min (was 2+ days)
- ✅ CTO time freed: 10 min/month on backlog approval (was 20+ hours/week on execution)
- ✅ Scalability: 5 kits without adding engineers (was 1 kit per 3 engineers)
- ✅ Quality: 2 suites every landing (was "developer says it works")
- ✅ Observability: Sweep + VERA discover defects automatically (was manual code review)
- ✅ Feedback: Metrics fed back to design (SRE → Issue → Router → Code → Shipped)

### Negative
- ⚠️ Complexity: 14 agents to understand and tune (mitigated by documentation)
- ⚠️ Debugging: When Squad fails, diagnostic work needed (mitigated by rich logs and verdicts)
- ⚠️ Human review gap: Code review no longer blocks integration (mitigated by test coverage + VERA)

### Neutral
- 🔄 CTO role evolves: less execution, more strategy (required for scaling)
- 🔄 Manager role evolves: less mentoring/pairing, more monitoring (natural progression)

---

## Related Decisions

- ADR-0020: Fleet Router — Intelligent Work Dispatch
- ADR-0021: Fleet Lander — Verified Integration
- ADR-0022: VERA — Autonomous Technical Arbiter
- ADR-0024: Squad Supervisor — Continuous Orchestration

---

## References

- AIDLC Workflows: https://github.com/awslabs/aidlc-workflows
- Squad Agent Manifest: `docs/SQUAD_AGENTS-HISTORICAL.md` (renamed 2026-09-21 — the name is what a reader sees before the HISTORICAL banner inside it)
- Squad Fleet Implementation: `mechanisms/fleet/`

---

**Approved by:** CTO (Paulo Henrique)  
**Stakeholders:** Architects (System, Domain, Platform), Product Owner, QA Lead, SRE Lead

---

*Version 1.0 — 2026-09-03*
