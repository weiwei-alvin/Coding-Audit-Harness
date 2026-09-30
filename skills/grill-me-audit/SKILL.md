---
name: grill-me-audit
description: Audit wrapper for grill-me that enforces Discovery stage acceptance criteria. Invokes the upstream grill-me skill and validates outputs against PLAN.md and README.md audit rules. Fails if upstream grill-me skill is unavailable.
---

# grill-me-audit

Audit wrapper for **grill-me** (Discovery stage). This skill invokes the upstream `grill-me` skill and enforces the Discovery audit rules below.

## Upstream Dependency

**Required**: `grill-me` (from `skills/matt-upstream/grill-me`)

If the upstream skill is not available, this skill **fails explicitly** — no silent fallback.

## Audit Rules

### PLAN.md Acceptance Criteria

- **PLAN-1. Target User**: Who is most likely to use this product? Who gets clear value?
- **PLAN-2. Current Pain Point**: What specific problem does the user face? In what context?
- **PLAN-3. Proposed Product / Solution**: What product/solution does V1 provide for the pain points?
- **PLAN-4. Problem–Solution Fit**: How does the solution directly improve the pain points? Each major solution must map to at least one explicit pain point.
- **PLAN-5. V1 In Scope**: What features/capabilities are explicitly included in V1?
- **PLAN-6. V1 Out of Scope**: What features are explicitly excluded from V1? No auto-inclusion based on "might need later".

### README.md Acceptance Criteria

- **README-1**: Describe only product positioning, target user, pain points, and V1 core capabilities — serves as external scope verification.
- **README-2**: Strictly forbidden: unverified implementation details, environment install commands, or API specs.
- **README-3**: Must not claim features undefined in PLAN.md; must not describe Out of Scope as delivered.
- **README-4**: Only after implementation completes may it be updated to include technical operation guides.

## Execution

1. Verify upstream `grill-me` skill exists at `skills/matt-upstream/grill-me/SKILL.md`. If not, **fail with error**.
2. Invoke upstream `grill-me` skill (via Skill tool) to conduct the interview and produce PLAN.md + README.md.
3. After upstream completes, validate outputs against the audit rules above.
4. Report any violations as blocking findings.

## Runner Integration

When the stage output is ready, run `python harness/runner/runner.py set-ready-for-gate`. The operator (not the agent) records the Gate result with `python harness/runner/runner.py gate-verdict --verdict PASS|FIX_REQUIRED|USER_DECISION_REQUIRED` (`--decision-ref DEC-NNN` for USER_DECISION_REQUIRED).

## Validation Checklist

- [ ] PLAN.md exists and contains all PLAN-1 through PLAN-6 sections
- [ ] Each PLAN section has substantive content (not placeholder)
- [ ] README.md exists and passes README-1 through README-4
- [ ] No implementation details in README.md
- [ ] No Out of Scope features claimed as delivered
- [ ] V1 In/Out of Scope are explicit and non-overlapping