# Coding Audit Harness 2.0 — SPEC.md

> Source of truth: `PLAN.md` (Status: PROPOSED · 2026-10-19)
> Stage output of `to-spec` / `to-spec-audit`
> Scope: local single-operator Audit Console, CLI recovery UX, onboarding and calculator demo

## Problem Statement

A developer using Coding Audit Harness can only learn the project state, inspect
verification receipts, and submit Gates or Review verdicts by reading JSON files
and composing CLI commands. The Runner already refuses unsafe completions, but the
operator has to reconstruct the current state, the approved plan, the evidence
bindings, and the legal next action by hand. This makes the first end-to-end run
slow, makes recovery from a stale hash or a paused project error-prone, and makes
it easy to mistake "tests passed" for "a human approved the result".

The same operator cannot see, in one place, whether the plan approved at the
TICKETS Gate still matches the files on disk, whether a receipt belongs to the
current source, or whether a review payload will be accepted before submitting it.

## Solution

Add a local, loopback-only **Audit Console** that reads the Runner's state and
controlled artifacts, presents them with progressive disclosure, prepares
schema-valid Gate/Review/Decision payloads, shows a preflight result and the
impact of the operation, and then delegates the actual write to the existing
Runner CLI. The Runner remains the only authority for state transitions,
evidence validation, and completion.

Alongside the Console:

- common CLI failures gain a stable error code, a plain-language reason, the
  affected state, and the legal next steps;
- the README first screen explains the value, audience, limits, and quick entry;
- a runnable calculator example demonstrates the full lifecycle without touching
  an existing `.harness` directory.

## Scope

The V2 MVP strictly inherits the In Scope items of `PLAN.md` section 2. No product
scope is added or expanded here.

| PLAN.md In Scope item | Traceability |
|---|---|
| README and onboarding; calculator example; manual demo retained | US-009 |
| CLI UX: readable error code, reason, affected state, legal next steps | US-010 |
| Audit Console: project summary, stage, active ticket, dependencies, approved plan, Golden Path evidence, receipts, handoff, findings, review history | US-001, US-002, US-003 |
| Gate operations at TICKETS with plan fingerprint and explicit confirmation | US-004 |
| T-001 review workflow (PASS / FIX_REQUIRED / USER_DECISION_REQUIRED) through Runner | US-005, US-006, US-007 |
| Failure recovery UX for stale hash, plan change, missing evidence, blocking finding, retry limit, PAUSED, concurrent conflict | US-008 |
| Runner-authoritative, evidence-first, progressive disclosure, safe by default, CLI parity | US-011, US-012 |

The Console reads a target project; it does not create a second state store. The
existing DISCOVERY/SPEC stages remain agent-assisted and are **not** enforced by
the Runner at stage level; the Console must say so rather than imply otherwise.

## User Stories

1. US-001: As a developer, I want one Overview that shows project status, pipeline stage, stage status, active ticket, ticket completion counts, current blockers, and the next legal action, so that I know where the project stands without reading JSON.
2. US-002: As a reviewer, I want to inspect every ticket's ID, title, status, direct dependencies, blocking reasons, and referenced User Stories and Golden Path steps, so that I can judge whether the approved plan is executable.
3. US-003: As a reviewer, I want machine execution evidence and human review judgment displayed in separate sections with receipt references, source hashes, verdicts, findings, and review rounds, so that I can trace every claim.
4. US-004: As an operator, I want to perform TICKETS Gate actions only after seeing the ticket graph, per-ticket Golden Path coverage, User Story coverage, and the current plan fingerprint, so that I explicitly approve the plan the Runner will enforce.
5. US-005: As a reviewer, I want to submit PASS only when review, handoff, and receipt bindings match, all controlled results are PASSED with return code 0, every required criterion is satisfied, and no blocking finding is open, so that completion is never claimed prematurely.
6. US-006: As a reviewer, I want to submit FIX_REQUIRED with at least one structured blocking finding that carries a stable finding key and criterion reference, so that corrective work is precise and continuity is preserved.
7. US-007: As an operator, I want to submit USER_DECISION_REQUIRED and to resolve pauses using only the Runner-supported options, rationale, and source, so that no unsupported override or PASS shortcut exists.
8. US-008: As an operator, I want explicit explanations and safe recovery steps for stale source hashes, approved-plan changes, missing evidence, blocking findings, retry limits, PAUSED projects, and concurrent state conflicts, so that I can recover without corrupting state.
9. US-009: As a new user, I want a calculator example that runs the full lifecycle in an isolated disposable directory and never overwrites an existing `.harness`, so that I can learn the workflow end to end.
10. US-010: As a CLI user, I want common failures to show a stable error code, reason, affected state, and legal next steps, so that I can recover without guessing or weakening safeguards.
11. US-011: As a security-conscious operator, I want the Console bound to loopback, protected against cross-origin requests, unable to write state or declare PASS itself, and able to add `--trust-commands` only after explicit per-operation consent, so that another local web page cannot approve or execute commands on my behalf.
12. US-012: As an existing V1 user, I want the current CLI commands, state transitions, and security boundaries to keep working after V2 is added, so that my existing workflow does not regress.

## V1 Golden Path

The executable form of these scenarios is `.harness/golden_path.json`, created in
the Tickets stage. Each line below maps a scenario to its User Stories and Ticket.

- GP-001: CLI recovery guidance is available for common failures (US-010, T-001) — `python harness/runner/test_cli_errors.py` — Expected: exit 0
- GP-002: Read-only Console shows Overview, Tickets, and rejects cross-origin writes (US-001, US-002, US-011, T-002) — `python harness/runner/test_console.py ConsoleReadTests` — Expected: exit 0
- GP-003: Evidence & Review separates machine evidence from human judgment and blocks unsafe PASS (US-003, US-005, US-006, US-007, T-003) — `python harness/runner/test_console.py ReviewTests` — Expected: exit 0
- GP-004: Gate and decision operations delegate to the Runner and expose recovery paths (US-004, US-007, US-008, T-004) — `python harness/runner/test_console.py GateDecisionTests` — Expected: exit 0
- GP-005: Calculator demo completes the lifecycle in an isolated directory (US-009, T-005) — `python examples/calculator/demo.py` — Expected: exit 0
- GP-006: Acceptance regression keeps V1 behavior and proves bad evidence cannot complete (US-008, US-012, T-006) — `python harness/runner/test_console.py AcceptanceTests` — Expected: exit 0

## Implementation Decisions

- **Transport and dependencies.** The Console is a Python standard-library HTTP
  server (`ThreadingHTTPServer`) serving local HTML/CSS/JS. No CDN, no build step,
  no framework, and no new runtime dependency. It binds `127.0.0.1` by default and
  refuses a non-loopback bind.
- **Runner authority.** All writes go through the existing Runner CLI in a
  subprocess. The Console preserves exit code, stdout, and stderr; it never writes
  `.harness/state.json`, receipts, decisions, or review history. Review payloads
  and handoffs are staged in the system temp directory, outside the project, so
  they cannot perturb the source hash.
- **Adapter boundary.** A read-only adapter turns state, ticket files, the pipeline
  definition, Golden Path steps, receipts, review artifacts, and decisions into view
  models. The adapter has no workflow state machine and no second source of truth.
- **Preflight, then Runner validation.** The Console validates payload shape against
  the existing schemas and checks the documented bindings before submission. The
  Runner re-validates everything; a local preflight pass is never treated as an
  approval.
- **Freshness.** Before a review or gate action, the Console re-reads state, the
  approved plan digest, and the current source hash. A mismatch is surfaced as a
  specific blocking reason, not auto-repaired.
- **Trust commands.** `--trust-commands` is never added implicitly. The request must
  carry an explicit operator consent flag, and the UI must display the exact
  commands, the OS-user permission context, and the no-sandbox limitation before
  the action becomes available.
- **Cross-origin protection.** POST requests require a per-process token, a
  same-loopback `Origin`, and a non-cross-site `Sec-Fetch-Site` value. Static
  responses are same-origin only; no permissive CORS headers are sent.
- **CLI error taxonomy.** A small mapping module produces
  `ERROR [HARNESS-<CODE>]`, reason, affected state, and legal next steps while
  preserving exit code 1 and the existing safety checks.
- **UI structure.** One page with four navigation entries: Overview, Tickets,
  Evidence & Review, Decisions. Status is conveyed with text and icon/shape, not
  color alone. Raw JSON, stdout, and stderr are behind progressive-disclosure
  elements.
- **Demo isolation.** The calculator demo copies the harness into a temporary
  directory, writes its own SPEC, tickets, and Golden Path there, and removes the
  directory on exit. It never writes to the repository's `.harness`.

## Testing Decisions

- Tests assert external behavior: HTTP responses, view-model fields, Runner state
  after an action, and process exit codes. They do not assert private helper calls.
- Every test project is disposable. Tests copy `harness/` into a temporary root and
  create tickets, SPEC, and `golden_path.json` there, following the existing
  `test_support.py` pattern.
- Review tests use real receipts produced by `verify-ticket` or the Workflow, so
  binding failures exercise the same code path as production.
- Failure tests must prove the bad action did not change state: stale hash, wrong
  `verification_id`, missing receipt, blocking finding, retry limit, plan change,
  and duplicate submit.
- Security tests must prove a cross-origin or token-less POST is rejected and that
  a GET never mutates state.
- The demo test must run the demo and assert the resulting state is COMPLETE in the
  temporary project, while the repository `.harness` is untouched.
- The full existing suite (`python harness/runner/run_tests.py`) must stay green.
- Each stage produces an `agy` review record under `docs/reviews/`.

## Out of Scope

- Agent runtime, direct LLM calls, MCP orchestration, scheduling, multi-user
  collaboration, login, and RBAC.
- Rewriting Golden Path acceptance, relaxing review conditions, or editing runtime
  state directly.
- Claiming a hash is a tamper-proof signature, or claiming the local web UI is a
  sandbox or security isolation boundary.
- New PASS overrides, ABORT, or INVALIDATE operations without an approved basis.
- Claiming DISCOVERY or SPEC are enforced at stage level by the Runner.
- Figma/Storybook integration, visual regression, pixel-perfect comparison, design
  asset management, and analytics dashboards.

## Further Notes

- **Trust boundary.** The Console's confirmation is an accident-prevention device,
  not identity verification or an enforced "human present" boundary. Any operator
  with the same OS permissions can edit the same files; the Console does not claim
  otherwise.
- **T-001 semantics.** The T-001 review flow in `PLAN.md` is a demonstration shape,
  not a hard-coded ticket ID. The Console must read the target project's active
  ticket and evidence.
- **Final ticket.** When the reviewed ticket is the last one, the Console tells the
  operator that the Runner will also run Final Integrated Verification; success is
  reported only after the Runner's committed state says COMPLETE.
- **Naming.** Repository name `Coding Audit Harness` is retained. The version is
  `Coding Audit Harness 2.0`; the UI is `Audit Console`; the verification core is
  `Harness Runner`; existing `Audit Skills` keep their names.
