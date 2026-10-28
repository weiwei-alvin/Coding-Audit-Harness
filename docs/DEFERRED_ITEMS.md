---
document_title: Deferred Items
chinese_title: 暫不實作項目
aka: []
established_date: null
updated_date: 2026-10-28
version: 1.2.0
---

# Deferred Items — Current status and open roadmap commitments (2026-10-28)

This is the **current deferred / not-fully-evidenced backlog**, not just the 2026-09-29 “Not in V1” list. The existing Python Runner and optional UI Pack do not imply every promise in the [V2 UI Design Integration roadmap](roadmap/v2-ui-design-integration.md) is delivered. **Partial** means that related code exists but the original complete acceptance criteria have not been demonstrated.

The `SPEC.md` required at a **target project's root** is that project's requirement source. The deferred SDAH Audit Console has its **separate** [PLAN](roadmap/audit-console/PLAN.md) and [SPEC](roadmap/audit-console/SPEC.md).

**Current approval boundary:** an agent with command access can submit `gate-verdict PASS` and `review-verdict PASS`. Runner checks structure, state and required receipts, but **does not authenticate a human approver**. Golden Path assertions may be authored by the agent; Runner runs them and binds results but **does not judge assertion coverage or quality**. Human review remains an external responsibility, not an enforced Gate.

---

## 1. Generic Web Dashboard (separate from Audit Console)

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
- LLM review quality varies; independent human review is recommended for critical decisions, but is not currently enforced by the Runner
- Cost unpredictability (token usage per PR)
- False positive/negative risk without human calibration
- Current: `code-review-audit` is agent-readable review guidance; human review must be arranged separately

**Reconsideration Trigger**:
- Team scales beyond capacity for manual reviews
- LLM review achieves consistent >95% accuracy on test corpus
- Budget approval for LLM review compute costs

---

## 5. Automated Ticket Generation from Spec

**Description**: LLM automatically generates tickets from a target project's `SPEC.md` without separately verified human sign-off.

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


## 11. Audit Console — deferred standalone milestone

**Specification:** [Audit Console PLAN](roadmap/audit-console/PLAN.md) · [Audit Console SPEC](roadmap/audit-console/SPEC.md).

**Not yet delivered:** the operator-facing local Web UI for Runner overview, controlled Gate/Review decisions, evidence inspection and recovery; its calculator demo `examples/calculator/`; and the planned `harness/runner/test_console.py` / `harness/runner/test_cli_errors.py`. These paths are **not in the repo**. Proposed Golden Path commands referring to them are not executable verification evidence. The current UI Pack validates **product UI quality**, not this separate operator console.

**Re-evaluation conditions:** approve an independent Audit Console scope and a loopback / cross-origin threat model; implement a disposable calculator lifecycle; prove UI writes delegate to Runner without bypassing Gate, evidence, review and retry requirements; add missing tests and CI evidence. A request for a generic dashboard alone is not proof of readiness.

## 12. Open commitments from original V2 milestones

These entries map **Milestones 0–11** in the [V2 UI Design Integration directive](roadmap/v2-ui-design-integration.md) to remaining requirements. Several have **partial** equivalents in the current `packs/ui/` JSON contract, DESIGN Gate, evidence collectors and browser E2E. Partial equivalents **do not** establish completion of the named original artifacts or generic enforcement. Each entry remains open until its closure evidence exists.

| Original milestone | Unfulfilled or not-demonstrated commitment | Re-evaluation / closure condition |
| --- | --- | --- |
| **M0 — Baseline Lock** | Required historical `docs/V2_BASELINE.md` (starting commit, results, known failures, V1 lifecycle) is missing; later CI results do not reconstruct the pre-V2 baseline. | Produce a provenance-marked baseline report from contemporaneous evidence, explicitly noting any unavailable historical facts; never backdate today's test run. |
| **M1 — UI Design Contract** | The named `rules/ui-design.md`, `UI-SPEC.md` and `DESIGN.md` contract artifacts were promised. Current `contract.json` and generated documentation are not proven to meet those *exact* outputs. | Approve an equivalent-artifact mapping or implement the named outputs; verify schema, UI flow/state/criterion coverage and compatibility. |
| **M2 — ui-design-audit Skill** | `skills/ui-design-audit/SKILL.md` is **not implemented**; an existing UI Pack CLI is not equivalent to the promised fail-closed conditional skill routing. | **DEFERRED by decision below;** meet its four re-evaluation conditions before implementation. |
| **M3 — UI State Machine** | Current UI pipeline uses `DESIGN`, not the proposed `UI_DESIGN`, and does not implement an explicit `UI_REQUIRED` / `UI_NOT_REQUIRED` decision with safe automatic stage skip in that pipeline. | Define a migration strategy and test both UI-required/no-UI flows, conditional Gate bypass prevention, and illegal transitions. |
| **M4 — UI Traceability** | UI contract references exist, but generic Runner traceability/ticket enforcement has not been shown to require `US → FLOW → SCREEN → UI-AC → Ticket` with orphan/dangling/UI-ticket checks. | Integrate UI graph into Runner ticket validation and reporting; add orphan, dangling, duplicate, and non-UI negative tests. |
| **M5 — UI Evidence Contract** | Collector hashes exist; a universal per-`UI-AC` structured receipt with ticket, screen, criterion, viewport and actual result is not fully established. | Enforce missing-screenshot, required-viewport, wrong-ticket and stale-evidence failures in normal UI ticket verification. |
| **M6 — Implementation Audit** | `skills/implement-audit/SKILL.md` does not provide the full UI-specific flow/screen/criterion minimum-context routing; required UI evidence is not universally enforced before Ready for Review. | Implement scoped UI-ticket context and UI evidence checks, protecting DESIGN changes via decisions; show UI and non-UI tests. |
| **M7 — UI Review** | The Pack has review/fix features, but the roadmap's UIR-1–UIR-6 dimensions and mandatory combined Functional+UI PASS are not proven for *all* UI tickets. **Gate and Review do not enforce a human submitter.** | Add per-UI-ticket negative cases enforcing critical UI review; separately design verifiable human approval if “human-only PASS” is to become a product guarantee. |
| **M8 — UI Fix Loop Memory** | UI Pack review/fix and Runner retry exist, but the requested *selective* next-attempt context and unified per-ticket UI finding continuity are not generally demonstrated. | Reproduce two review rounds with scoped screenshot/rule/finding context, stable `finding_key` and existing retry/pause behavior. |
| **M9 — Final Integrated UI Verification** | One built-in Chromium flow is verified; universal blocking of COMPLETE when *any* critical UI-AC lacks current evidence has not been shown for arbitrary projects. | Require current per-criterion evidence and approved UI Golden Path for multiple fixtures, including missing/stale evidence negatives. |
| **M10 — Full V2 Regression Matrix** | CI and one UI E2E fixture exist, but the separate **no-UI routing** fixture and the directive's full list of 16 negative/routing cases are not reconciled to real test IDs. | Map all 16 listed cases to executable tests and add both UI-required and UI-not-required E2E workflows. |
| **M11 — Documentation & V2 Release** | The promised `docs/V2_UI_DESIGN.md` does not exist; original stage/artifact naming differs from current code. | Publish a verified implementation-vs-roadmap document and recheck every public path, stage, command, schema and release claim. |

### M2 decision: defer `ui-design-audit` until its contract and routing are testable

**Decision as of 2026-10-28: DEFER, not implemented.** Do not add a nonfunctional `skills/ui-design-audit/SKILL.md` merely to satisfy a file-existence check. Existing UI contract and guidance commands remain available but are **not** that Skill.

**Re-evaluate only after all four conditions hold:** (1) the canonical UI contract and mapping to `UI-SPEC.md` / `DESIGN.md` are explicitly approved; (2) required upstream skills, conditional routing and fail-closed behavior are specified; (3) tests cover missing required capability, no silent fallback, explicit `UI_NOT_REQUIRED`, and no frontend code writes; (4) an owner approves implementation and maintenance scope. Implement through Discovery → Spec → Tickets → Implementation; require both promised artifact formats to validate before marking M2 complete.

**Release caveat:** 201 green Python tests and 37 passing UI fixture checks do not by themselves close M0–M11. These are outstanding *original-roadmap* commitments or equivalence decisions, not claims that the current UI Pack is nonfunctional.

---

## Process for Reconsideration

To move a deferred item to active (these approval steps are **policy**, not a Runner-enforced human authorization boundary):

1. **File a formal requirement** through Discovery (grill-me-audit)
2. **Create SPEC** via to-spec-audit with clear problem statement
3. **Decompose to Tickets** via to-tickets-audit
4. **Get stakeholder approval** on scope and priority
5. **Implement** through normal harness flow

Do not close an outstanding milestone from a prose assertion or one successful example: require a recorded scope decision, implementation, applicable negative tests and evidence for the closure conditions above.