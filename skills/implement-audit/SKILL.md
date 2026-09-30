---
name: implement-audit
description: Audit wrapper for implement that enforces Implementation stage acceptance criteria. Invokes the upstream implement skill and validates outputs against implementation audit rules. Fails if upstream implement skill is unavailable.
---

# implement-audit

Audit wrapper for **implement** (Implementation stage). This skill invokes the upstream `implement` skill and enforces the Implementation audit rules below.

## Upstream Dependency

**Required**: `implement` (from `skills/matt-upstream/implement`)

If the upstream skill is not available, this skill **fails explicitly** — no silent fallback.

## Audit Rules

### Implementation Acceptance Criteria

- **IMPL-1. Ticket Fidelity**:
  - Implementation scope must match current Ticket's goals and acceptance criteria
  - Every significant code change must explain how it supports current Ticket
  - No self-added features or speculative work beyond Ticket requirements

- **IMPL-2. Working Outcome**:
  - Ticket's required functionality must actually work / produce expected results
  - Developer must verify Ticket acceptance criteria — not just "code runs" or "build passes"

- **IMPL-3. Verification Evidence**:
  - Developer must provide evidence Reviewer can reproduce
  - Required automated evidence comes only from `python harness/runner/runner.py verify-ticket --ticket T-<NNN> --trust-commands`, which runs every enabled Golden Path step and saves a receipt. A failing or UNVERIFIED step blocks completion; fix the code and run it again (old receipts are never reused)
  - Evidence must include:
    - Actual verification steps/commands executed
    - Expected results
    - Actual results
    - Verifiable test logs, output, or records

- **IMPL-4. Test Relevance**:
  - Tests must directly verify Ticket Acceptance Criteria or key behaviors
  - Tests must have **breakage detection**: if functionality is deliberately broken, test must FAIL
  - Forbidden: tautological assertions, empty tests with no real verification, over-mocking that bypasses core business logic
  - If Acceptance Criterion unsuitable for automation, must use reproducible manual steps with log/screenshot evidence

- **IMPL-5. Handoff Completeness**:
  - Each completed Ticket requires a Handoff payload at `.harness/inbox/handoff.json`: a plain JSON file (no Markdown) conforming to `harness/handoff.schema.json`
  - Copy the four binding fields exactly from the latest `verify-ticket` output: `ticket_id`, `review_round`, `source_hash`, `verification_id`. Any code change after that run invalidates them; rerun `verify-ticket`
  - Handoff content:
    - `changes`: actual changes and behavioral differences, per key modified file
    - `verification`: steps, expected results, actual results (`status` is PASS or UNVERIFIED)
    - `dependencies`
  - Optional human-readable narrative may go in `.harness/handoffs/T-<NNN>.md`; the Runner does not read it
  - Example:
    ```json
    {"ticket_id": "T-001", "review_round": 1, "source_hash": "<from verify-ticket>", "verification_id": "<from verify-ticket>",
     "changes": [{"file": "calc.py", "summary": "Add addition"}],
     "verification": [{"step": "python check_calc.py", "expected": "exit 0", "actual": "exit 0", "status": "PASS"}],
     "dependencies": []}
    ```
  - Exception Handling:
    - Items unverifiable due to env/permissions/tool limits **must be marked [UNVERIFIED]**
    - No describing planned/unexecuted/unconfirmed items as verified pass

- **IMPL-6. Approved Plan Is Read-only**:
  - Do not edit `.harness/tickets/`, `.harness/golden_path.json` or `SPEC.md` during implementation. Weakening a verification command or narrowing a Ticket to make it pass is forbidden
  - Any such change pauses the project (`PLAN_CHANGE_REQUIRES_DECISION`) until the operator reviews it with `decide` and `resume`
  - If the plan is wrong, stop and report it instead of editing it

## Execution

1. Verify upstream `implement` skill exists at `skills/matt-upstream/implement/SKILL.md`. If not, **fail with error**.
2. Invoke upstream `implement` skill to implement the active Ticket (`python harness/runner/status.py --json` shows it).
3. Run `python harness/runner/runner.py verify-ticket --ticket T-<NNN> --trust-commands` until every step passes.
4. Write `.harness/inbox/handoff.json` with the binding fields from the final run.
5. Run `python harness/runner/runner.py mark-ticket-ready-for-review --ticket T-<NNN>`.
6. Validate outputs against the audit rules and report any violations as blocking findings.

## Validation Checklist

- [ ] Implementation scope matches Ticket goals/acceptance criteria
- [ ] All significant changes trace to Ticket requirements
- [ ] No speculative/unrequested features added
- [ ] Functionality actually works (not just builds)
- [ ] Developer verified acceptance criteria (not just "no errors")
- [ ] Verification evidence provided (steps, expected, actual, logs)
- [ ] Tests verify acceptance criteria/key behaviors
- [ ] Tests have breakage detection (fail when broken)
- [ ] No tautological/empty/over-mocked tests
- [ ] Manual verification has log/screenshot evidence
- [ ] `verify-ticket` passed on the final code; no later code changes
- [ ] `.harness/inbox/handoff.json` exists, is plain JSON and matches `handoff.schema.json`
- [ ] Binding fields copied exactly from the latest `verify-ticket` output
- [ ] Tickets, `golden_path.json` and `SPEC.md` untouched
- [ ] Unverifiable items marked [UNVERIFIED]