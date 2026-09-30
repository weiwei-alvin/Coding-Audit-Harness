---
document_title: Deferred Items
chinese_title: 暫不實作項目
aka: []
established_date: null
updated_date: 2026-09-29
version: 1.1.0
---

# Deferred Items - Not in V1

The following items are explicitly **deferred** from V1. They will not be implemented unless they go through the formal requirements process (Discovery → Spec → Tickets → Implementation).

---

## 1. Web Dashboard

**Description**: Visual web UI for monitoring harness state, ticket progress, findings, and traceability.

**Why Deferred**:
- CLI + status command + markdown reports provide sufficient observability
- Web UI adds significant complexity (frontend, backend, auth, real-time updates)
- Not required for core harness functionality

**Reconsideration Trigger**:
- Team grows beyond 5 engineers needing parallel visibility
- Stakeholder demand for non-technical dashboard
- Integration with existing observability platform

---

## 2. Fixed Token Budget

**Description**: Hard token limits for context expansion (e.g., "max 8000 tokens per agent").

**Why Deferred**:
- Symbol-first context expansion is a documented practice; no runtime enforcement is claimed
- Token budgets are arbitrary and often counterproductive
- Different tasks need different context sizes
- Better to expand until question answered than hit artificial limit

**Reconsideration Trigger**:
- Consistent context overflow issues in production
- Cost control requirements from LLM provider billing
- Specific model with strict context window constraints

---

## 3. Additional Golden Path Framework

**Description**: Extended golden path verification framework beyond the incremental verification in Task 11.

**Why Deferred**:
- Current incremental + final verification covers requirements
- Additional framework (parallel paths, negative paths, chaos testing) adds complexity
- Can be added per-project as needed

**Reconsideration Trigger**:
- Multiple independent golden paths needed
- Regulatory requirement for specific verification patterns
- Integration with external test management tools

---

## 4. CI Auto-calling LLM Reviewer

**Description**: CI pipeline automatically invokes LLM for code review on every PR/commit.

**Why Deferred**:
- LLM review quality varies; human review still required for critical decisions
- Cost unpredictability (token usage per PR)
- False positive/negative risk without human calibration
- Current: Human reviewer uses `code-review-audit` skill with LLM assistance

**Reconsideration Trigger**:
- Team scales beyond capacity for manual reviews
- LLM review achieves consistent >95% accuracy on test corpus
- Budget approval for LLM review compute costs

---

## 5. Automated Ticket Generation from Spec

**Description**: LLM automatically generates tickets from SPEC.md without human approval.

**Why Deferred**:
- Ticket decomposition requires architectural judgment (vertical slicing, dependency identification)
- Current: `to-tickets-audit` with human approval loop works well
- Risk of over/under-decomposition without human oversight

**Reconsideration Trigger**:
- SPEC.md format standardized with explicit decomposition hints
- LLM achieves consistent ticket quality matching senior engineer
- Team velocity bottleneck at ticket creation stage

---

## 6. Cross-repo Traceability

**Description**: Traceability links spanning multiple repositories (monorepo or multi-repo).

**Why Deferred**:
- Single-repo traceability covers V1 scope
- Cross-repo requires shared ID registry or federated system
- Adds distributed systems complexity

**Reconsideration Trigger**:
- Project splits into multiple repositories
- Platform team needs cross-service impact analysis
- Architecture review identifies cross-repo dependencies

---

## 7. Natural Language Query Interface

**Description**: "Ask harness questions in plain English" (e.g., "Which tickets block T-005?").

**Why Deferred**:
- CLI commands + status + traceability provide precise queries
- NL interface adds ambiguity and hallucination risk
- Structured queries are more reliable for automation

**Reconsideration Trigger**:
- Non-technical stakeholders need direct access
- LLM query accuracy reaches 100% on test suite
- Integration with Slack/Teams for chatops

---

## 8. Automated Dependency Resolution

**Description**: Runner automatically reorders/resolves ticket dependencies instead of failing.

**Why Deferred**:
- Explicit dependency declaration forces architectural clarity
- Auto-resolution hides design problems
- Current: `validate-deps` catches issues early

**Reconsideration Trigger**:
- Frequent dependency conflicts in practice
- Team adopts explicit architecture decision records (ADRs)
- Tooling matures for safe auto-resolution

---

## 9. Real-time Collaboration / Multi-agent Sessions

**Description**: Multiple agents (or human+agent) working on same harness state simultaneously.

**Why Deferred**:
- Single-agent sequential execution is simpler and more auditable
- Local state lock and stale-writer rejection are implemented; collaborative merge/conflict resolution remains deferred
- Current: Handoff artifacts support sequential handoff; no simultaneous multi-agent runtime

**Reconsideration Trigger**:
- Team adopts pair-programming with agents
- Harness state becomes bottleneck for parallel work
- Infrastructure supports distributed state (e.g., CRDTs)

---

## 10. Historical Analytics / Metrics Dashboard

**Description**: Long-term metrics (cycle time, review attempts, finding recurrence, velocity).

**Why Deferred**:
- Current: Status command + handoff artifacts provide immediate visibility
- Analytics require data warehouse / time-series DB
- Can be built on top of exported session data later

**Reconsideration Trigger**:
- Management requests velocity/quality reports
- Team adopts DORA metrics or similar framework
- Sufficient historical data accumulated (>100 tickets)

---

## Process for Reconsideration

To move a deferred item to active:

1. **File a formal requirement** through Discovery (grill-me-audit)
2. **Create SPEC** via to-spec-audit with clear problem statement
3. **Decompose to Tickets** via to-tickets-audit
4. **Get stakeholder approval** on scope and priority
5. **Implement** through normal harness flow

No deferred item enters V1 without this full process.