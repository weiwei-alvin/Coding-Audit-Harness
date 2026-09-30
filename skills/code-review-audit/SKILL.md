---
name: code-review-audit
description: Audit wrapper for code-review that enforces Review stage acceptance criteria. Invokes the upstream code-review skill and validates outputs against review audit rules. Fails if upstream code-review skill is unavailable.
---

# code-review-audit

Audit wrapper for **code-review** (Review stage). This skill invokes the upstream `code-review` skill and enforces the Review audit rules below.

## Upstream Dependency

**Required**: `code-review` (from `skills/matt-upstream/code-review`)

If the upstream skill is not available, this skill **fails explicitly** — no silent fallback.

## Audit Rules

### Review Acceptance Criteria

- **REV-1. Requirement Verification**:
  - Reviewer must verify against Ticket goals and Acceptance Criteria
  - Must NOT judge PASS based only on Developer Handoff, test results, or completion claims
  - Must confirm actual implementation achieves Ticket's required results

- **REV-2. Independent Verification**:
  - Reviewer should independently verify key evidence supporting Ticket PASS within available tools/env
  - If execution environment available (Terminal, Test Runner, Browser): must re-run and verify core Acceptance Criteria / high-risk changes
  - If no execution environment: only Evidence Inspection (cross-reference Code Diff, Handoff, test output) — must NOT claim actual functional verification
  - Any key items not personally executed must be marked **[UNVERIFIED]** in Review Verdict

- **REV-3. Scope Adherence**:
  - Reviewer must check all actual changes map to current Ticket
  - If Ticket-unrequested features/abstractions/frameworks/refactors found: must demand Developer justify necessity
  - If cannot link to Acceptance Criterion or necessary technical need → list as unnecessary change
  - Unnecessary changes must NOT be retained for "might need later"

- **REV-4. Code Quality**:
  - Reviewer must check code is clear, reasonable, maintainable
  - Special checks:
    - Obvious duplication or unnecessary complexity
    - Error-prone logic
    - Proper error handling
    - No regression risk to existing functionality
  - Must NOT demand new abstractions/frameworks/large refactors just for "prettier architecture"

- **REV-5. Finding Continuity**:
  - Every Finding must carry `finding_key` (per `finding.schema.json`): stable slug identifying same issue across Review rounds within a Ticket
  - If issue matches prior Review (from active findings in Review Context): **must reuse same `finding_key`**, no renaming
  - Only genuinely new, different-nature issues may use new `finding_key`

- **REV-6. Final Integrated Verification**:
  - If current Ticket is the last V1 Ticket (all others COMPLETE in `status.py --json`), the Runner itself re-runs every Golden Path step before accepting PASS; a failure blocks completion
  - Reviewer must additionally add a manual criterion `{"id": "FINAL_INTEGRATION", "status": "PASS", "critical": true, "source": "...", "limitations": "..."}` covering:
    - Full test suite
    - Overall behavior check against all User Stories
  - `source` states who observed what and where; `limitations` states what was not covered. The Runner rejects a critical manual criterion without both
  - If Final Integrated Verification fails → Verdict = FIX_REQUIRED, record as normal Finding

- **REV-7. Review Verdict** (only these three):
  - **PASS**: Core acceptance criteria met; sufficient verification evidence; core verifications done; no unverified critical items; non-critical [UNVERIFIED] explicitly listed; no blocking issues; no scope creep; no major code quality issues; if last Ticket, Final Integrated Verification passed
  - **FIX_REQUIRED**: Incomplete criteria, functional errors, regression, unnecessary implementation, failed Final Integrated Verification, or other Developer-fixable issues
  - **USER_DECISION_REQUIRED**: Issue involves requirements/scope/behavior tradeoffs Reviewer cannot decide under current SPEC/Ticket

### Review Payload Format

Write `.harness/inbox/review.json` as a plain JSON file (no Markdown) conforming to `harness/review-result.schema.json`. Optional narrative may go in `.harness/review-notes/T-<NNN>.md` (not `.harness/reviews/`, which holds Runner artifacts); the Runner does not read it.

- **PASS**: copy `ticket_id`, `review_round`, `source_hash`, `verification_id` exactly from the Developer's latest `verify-ticket` receipt (same values as `.harness/inbox/handoff.json`). `criteria` must contain one `critical: true`, `status: "PASS"` entry per Golden Path step in that receipt, using the step ID (e.g. `GP-001`) as `id`. Other critical criteria are manual and need `source` and `limitations`. Non-critical criteria may be FAIL or UNVERIFIED. `findings` is `[]`
- **FIX_REQUIRED**: `ticket_id`, the next `review_round`, and `source_hash` from `python harness/runner/runner.py snapshot`; no `verification_id` or handoff needed. At least one finding: `{"finding_key": "wrong-addition", "criterion_ref": "GP-001", "description": "...", "blocking": true}`
- **USER_DECISION_REQUIRED**: same binding as FIX_REQUIRED plus `decision_context`; its only option may be `FIX_REQUIRED`

Example PASS payload:

```json
{"ticket_id": "T-001", "review_round": 1, "source_hash": "<from receipt>", "verification_id": "<from receipt>",
 "verdict": "PASS", "criteria": [{"id": "GP-001", "status": "PASS", "critical": true}], "findings": []}
```

The Runner refuses PASS while any OPEN or REOPENED blocking finding remains for the Ticket. Run `resolve-finding --finding-id F-NNN` only after confirming the fix; the same `finding_key` appearing again reopens it.

## Execution

1. Verify upstream `code-review` skill exists at `skills/matt-upstream/code-review/SKILL.md`. If not, **fail with error**.
2. Invoke upstream `code-review` skill to review the changes.
3. Validate review outputs against the audit rules.
4. Write `.harness/inbox/review.json` and submit it:
   - PASS: `python harness/runner/runner.py review-verdict --ticket T-<NNN> --verdict PASS --review .harness/inbox/review.json --handoff .harness/inbox/handoff.json --trust-commands`
   - FIX_REQUIRED / USER_DECISION_REQUIRED: `python harness/runner/runner.py review-verdict --ticket T-<NNN> --verdict FIX_REQUIRED --review .harness/inbox/review.json`
5. A non-zero exit means the verdict was not recorded; read the error, fix the payload or evidence, and resubmit. Never edit `.harness/state.json`, Tickets, `golden_path.json` or `SPEC.md` to get past a refusal.

## Validation Checklist

- [ ] Review based on Ticket goals/acceptance criteria (not just Handoff/tests/claims)
- [ ] Actual implementation confirmed to achieve required results
- [ ] Independent verification performed where environment permits
- [ ] Unverified key items marked [UNVERIFIED] in Verdict
- [ ] All changes traced to Ticket; unjustified extras flagged
- [ ] No retention of unnecessary changes for "future"
- [ ] Code quality checked (duplication, complexity, errors, regressions)
- [ ] No architecture-prettiness demands for new abstractions
- [ ] All Findings carry stable `finding_key`
- [ ] Reused `finding_key` for recurring issues; new keys only for genuinely new issues
- [ ] If last V1 Ticket: `FINAL_INTEGRATION` criterion with `source` and `limitations`
- [ ] Verdict is only PASS / FIX_REQUIRED / USER_DECISION_REQUIRED
- [ ] `.harness/inbox/review.json` is plain JSON matching `review-result.schema.json`
- [ ] Binding fields match the receipt (PASS) or `snapshot` (other verdicts)
- [ ] One critical PASS criterion per Golden Path step in the receipt