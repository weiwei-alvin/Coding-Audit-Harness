---
name: to-tickets-audit
description: Audit wrapper for to-tickets that enforces Tickets stage acceptance criteria. Invokes the upstream to-tickets skill and validates outputs against ticket audit rules. Fails if upstream to-tickets skill is unavailable.
---

# to-tickets-audit

Audit wrapper for **to-tickets** (Tickets stage). This skill invokes the upstream `to-tickets` skill and enforces the Tickets audit rules below.

## Upstream Dependency

**Required**: `to-tickets` (from `skills/matt-upstream/to-tickets`)

If the upstream skill is not available, this skill **fails explicitly** — no silent fallback.

## Audit Rules

### Ticket Acceptance Criteria

- **TKT-1. Traceability**:
  - Every Ticket must trace to a User Story, approved product requirement, or valid Technical Ticket
  - No Tickets without explained requirement source
  - No Tickets for "might need later" abstractions, frameworks, plugin systems, generic interfaces

- **TKT-2. Single Outcome**:
  - One Ticket = one clear, verifiable outcome
  - No packing multiple independent functions/purposes into one Ticket

- **TKT-3. Vertical Slice for User-facing Features**:
  - User-facing feature Tickets must be vertical slices
  - Must include all necessary: UI, business logic, API endpoints, data models, persistence, validation, tests
  - No splitting frontend/backend/database into separate non-value-delivering Tickets

- **TKT-4. Technical Tickets**:
  - Only for shared technical work not attributable to a single User Story (global CI/CD, project-wide security updates, shared infra init)
  - Direct User Story work (UI, logic, API, data, persistence, validation, tests) must stay in that User Story's vertical slice
  - Technical Ticket creation must document:
    1. Why it can't fit in any single Vertical Slice
    2. Which approved requirements it supports
    3. Independent verification steps and acceptance criteria

- **TKT-5. Independently Verifiable**:
  - Every Ticket must have clear verification method
  - Must be independently judgeable PASS/FAIL — no "verify all together later"
  - Every Ticket must have at least one executable step in `.harness/golden_path.json` whose `ticket_ids` contain only that Ticket and, optionally, its prerequisites (direct or indirect `depends_on`). The step's command must contain a real assertion and exit non-zero on failure
  - End-to-end steps that span several Tickets (SPEC-3) are allowed in addition; they only run once all their Tickets are COMPLETE, so they can never be a Ticket's only verification
  - The TICKETS Gate refuses PASS when any Ticket lacks such a step, when a step has no command, or when a step references an unknown Ticket
  - Every step's `user_story_ids` names the SPEC.md User Stories it proves (never empty), and every SPEC.md User Story is covered by at least one step with a command. The assertion must check the behavior that story describes; a step that only proves the code runs does not verify a story. The Gate refuses PASS when SPEC.md is missing, defines no `US-NNN` stories, or any of these links is broken

- **TKT-6. Dependency Declaration**:
  - Each Ticket file (`.harness/tickets/T-<NNN>.md`) must declare `depends_on` field with dependent Ticket IDs (empty array `[]` if none)
  - `depends_on` can only reference Tickets in same approved batch
  - No circular dependencies (A→B, B→A)
  - Runner uses `depends_on` for execution order: only when all dependencies are COMPLETE can Ticket enter IMPLEMENTATION
  - If multiple Tickets are ready, Runner picks the smallest ticket filename (T-001 before T-002) — no autonomous prioritization. Number Tickets in the intended order
  - Supported syntax: `depends_on: [T-001, T-002]` or `depends_on: []`. Multiline YAML lists, quoted values and scalars are rejected

### Ticket File Format Example
```markdown
---
id: T-003
depends_on: [T-001, T-002]
---

# T-003: Ticket Title

**What to build:** end-to-end behavior from user perspective

**Blocked by:** T-001, T-002

**Status:** ready-for-agent

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2
```

### golden_path.json Example

```json
{
  "steps": [
    {"id": "GP-001", "description": "Login works", "user_story_ids": ["US-001"], "ticket_ids": ["T-001"],
     "verification_command": ["python", "-m", "pytest", "tests/test_login.py"], "expected_output": ""},
    {"id": "GP-002", "description": "Reset password", "user_story_ids": ["US-002"], "ticket_ids": ["T-001", "T-002"],
     "verification_command": ["python", "-m", "pytest", "tests/test_reset.py"], "expected_output": ""}
  ],
  "source_hash_exclude": [".coverage", "htmlcov", "dist"],
  "env_passthrough": []
}
```

- GP-001 covers T-001 alone; GP-002 covers T-002 plus its prerequisite T-001. Both are valid per-Ticket steps
- `source_hash_exclude` (optional): relative glob patterns for files the verification commands generate (coverage data, build output, logs). Without it, a command that writes into the project makes `verify-ticket` fail with "Project changed during verification". Patterns cannot cover `.harness`, `*` or the whole project; excluding source files would let changes to them go unnoticed
- `env_passthrough` (optional): extra environment variable names the commands need. Toolchain paths (HOME, USERPROFILE, APPDATA, LOCALAPPDATA, PATH, TEMP …) are passed by default; tokens and other variables are not
- Prefer argv arrays; string commands run through the shell

## Runner Integration

1. Write Ticket files and `.harness/golden_path.json`, then run `python harness/runner/runner.py set-ready-for-gate`.
2. The operator runs `python harness/runner/runner.py gate-verdict --verdict PASS`. The Runner checks the dependency graph, TKT-5 Ticket coverage and User Story coverage, records the approved plan digest (Ticket files, `golden_path.json`, `SPEC.md`), and starts the first ready Ticket.
3. After the Gate, any change to those files pauses the project on the next `verify-ticket` or `review-verdict` (reason `PLAN_CHANGE_REQUIRES_DECISION`). The operator reviews the change, runs `decide --option CONTINUE --rationale ... --source ...`, then `resume`. New Tickets are added as TODO; removing approved Tickets is not supported.

## Execution

1. Verify upstream `to-tickets` skill exists at `skills/matt-upstream/to-tickets/SKILL.md`. If not, **fail with error**.
2. Invoke upstream `to-tickets` skill to break spec/conversation into tickets.
3. After upstream completes, validate all generated tickets against audit rules.
4. Report any violations as blocking findings.

## Validation Checklist

- [ ] Every Ticket has traceability to User Story / approved requirement / valid Technical Ticket
- [ ] Every Golden Path step names the User Stories it proves; every SPEC.md User Story has a step
- [ ] No Tickets for speculative abstractions/frameworks
- [ ] Each Ticket has single clear outcome
- [ ] User-facing Tickets are vertical slices (full stack)
- [ ] Technical Tickets meet TKT-4 criteria with required documentation
- [ ] All Tickets independently verifiable
- [ ] Every Ticket has a `golden_path.json` step limited to itself and its prerequisites, with a real assertion command
- [ ] Commands that write files into the project have matching `source_hash_exclude` patterns
- [ ] `depends_on` declared in each Ticket file (`.harness/tickets/T-<NNN>.md`), valid references, no cycles
- [ ] Ticket numbering matches intended execution order
- [ ] Ticket file format matches specification