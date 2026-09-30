---
name: to-spec-audit
description: Audit wrapper for to-spec that enforces Spec stage acceptance criteria. Invokes the upstream to-spec skill and validates outputs against SPEC.md audit rules. Fails if upstream to-spec skill is unavailable.
---

# to-spec-audit

Audit wrapper for **to-spec** (Spec stage). This skill invokes the upstream `to-spec` skill and enforces the Spec audit rules below.

## Upstream Dependency

**Required**: `to-spec` (from `skills/matt-upstream/to-spec`)

If the upstream skill is not available, this skill **fails explicitly** — no silent fallback.

## Audit Rules

### SPEC.md Contents Required

1. V1 Scope
2. User Stories
3. V1 Golden Path

### SPEC.md Acceptance Criteria

- **SPEC-1. Scope Mapping & Traceability**:
  - SPEC.md must NOT reinterpret, expand, or add product scope — must strictly inherit approved V1 In Scope from PLAN.md
  - V1 Scope in SPEC.md serves only as traceability anchor: every approved feature must map to 1+ specific User Stories
  - No Scope without User Story mapping; no User Story without Scope source

- **SPEC-2. User-facing Behavior**:
  - Every User Story must describe behavior the user can actually perform or observe

- **SPEC-3. V1 Golden Path**:
  - Must define at least one V1 golden path / end-to-end scenario connecting multiple User Stories
  - Each golden path step must map to a specific User Story
  - Golden path must have verifiable Acceptance Criteria; before the last Ticket can complete, the Runner re-runs every Golden Path step as Final Integrated Verification
  - SPEC.md Golden Path lines describe end-to-end scenarios. The executable version is `.harness/golden_path.json`, created in the Tickets stage (to-tickets-audit TKT-5), where each Ticket also gets its own step. When that file exists the Runner ignores SPEC.md Golden Path lines
  - Line format if SPEC.md is used directly: `` - GP-NNN: Description (US-XXX, T-YYY) - `command` - Expected: text `` (Expected is optional)

- **SPEC-4. No Technical Stories**:
  - Pure technical work (database, API layer, cache, refactor, framework) must NOT be User Stories
  - Exception: only if they directly form user-observable product capabilities

## Runner Integration

When the stage output is ready, run `python harness/runner/runner.py set-ready-for-gate`. The operator (not the agent) records the Gate result with `python harness/runner/runner.py gate-verdict --verdict PASS|FIX_REQUIRED|USER_DECISION_REQUIRED` (`--decision-ref DEC-NNN` for USER_DECISION_REQUIRED).

## Execution

1. Verify upstream `to-spec` skill exists at `skills/matt-upstream/to-spec/SKILL.md`. If not, **fail with error**.
2. Invoke upstream `to-spec` skill to produce SPEC.md from conversation context.
3. After upstream completes, validate SPEC.md against the audit rules above.
4. Report any violations as blocking findings.

## Validation Checklist

- [ ] SPEC.md exists with V1 Scope, User Stories, V1 Golden Path sections
- [ ] V1 Scope strictly matches PLAN.md approved In Scope (no additions/expansions)
- [ ] Every Scope item maps to ≥1 User Story; every User Story maps to a Scope item
- [ ] All User Stories describe user-observable behavior
- [ ] At least one Golden Path defined with steps mapping to User Stories
- [ ] Golden Path has verifiable Acceptance Criteria
- [ ] No technical stories (database, API, cache, refactor, framework) as User Stories