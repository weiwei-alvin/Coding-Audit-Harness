#!/usr/bin/env python3
"""
State Transition Engine for Harness

Enforces all valid state transitions per Harness spec.
- Rejects undefined transitions
- Developer cannot directly set Ticket to COMPLETE
- Only Review PASS can complete Ticket
"""

from datetime import datetime
from enum import Enum
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass

from pipeline_definition import PipelineDefinitionError, definition_for_state, resolve_definition


class ProjectStatus(Enum):
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"


class PipelineStage(Enum):
    DISCOVERY = "DISCOVERY"
    SPEC = "SPEC"
    TICKETS = "TICKETS"
    IMPLEMENTATION = "IMPLEMENTATION"
    REVIEW = "REVIEW"


class StageStatus(Enum):
    IN_PROGRESS = "IN_PROGRESS"
    READY_FOR_GATE = "READY_FOR_GATE"


class TicketStatus(Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    COMPLETE = "COMPLETE"
    INVALIDATED = "INVALIDATED"
    PAUSED = "PAUSED"


class FindingStatus(Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    REOPENED = "REOPENED"


class ReviewVerdict(Enum):
    PASS = "PASS"
    FIX_REQUIRED = "FIX_REQUIRED"
    USER_DECISION_REQUIRED = "USER_DECISION_REQUIRED"


class GateVerdict(Enum):
    PASS = "PASS"
    FIX_REQUIRED = "FIX_REQUIRED"
    USER_DECISION_REQUIRED = "USER_DECISION_REQUIRED"


class PauseReason(Enum):
    GATE_USER_DECISION_REQUIRED = "GATE_USER_DECISION_REQUIRED"
    REVIEW_USER_DECISION_REQUIRED = "REVIEW_USER_DECISION_REQUIRED"
    RETRY_LIMIT_REACHED = "RETRY_LIMIT_REACHED"
    PLAN_CHANGE_REQUIRES_DECISION = "PLAN_CHANGE_REQUIRES_DECISION"


@dataclass
class TransitionResult:
    success: bool
    new_state: Optional[Dict] = None
    error: Optional[str] = None


class StateTransitionEngine:
    """
    Enforces all valid state transitions for the Harness.

    State Model:
    - Project Status: IN_PROGRESS | PAUSED | COMPLETE
    - Pipeline Stage: any stage declared by the resolved pipeline definition
    - Stage Status: IN_PROGRESS | READY_FOR_GATE
    - Active Ticket: T-<NNN> | null
    - Pause: {reason, decision_ref} | null
    - Tickets: {T-<NNN>: {status, review_attempts, active_findings}}
    - Findings: {F-<NNN>: {ticket_id, finding_key, status, ...}}

    The stage set, order, gate verdicts and hooks come from the definition file.
    The PipelineStage enum below is retained only as a compatibility alias for
    callers that still import the historical names; it is not authoritative.
    """

    # Valid Ticket Status Transitions
    TICKET_TRANSITIONS = {
        TicketStatus.TODO: [TicketStatus.IN_PROGRESS, TicketStatus.INVALIDATED],
        TicketStatus.IN_PROGRESS: [TicketStatus.READY_FOR_REVIEW, TicketStatus.PAUSED, TicketStatus.INVALIDATED],
        TicketStatus.READY_FOR_REVIEW: [TicketStatus.COMPLETE, TicketStatus.IN_PROGRESS, TicketStatus.PAUSED, TicketStatus.INVALIDATED],
        TicketStatus.COMPLETE: [],  # Terminal state
        TicketStatus.INVALIDATED: [TicketStatus.TODO],  # Can be re-planned
        TicketStatus.PAUSED: [TicketStatus.IN_PROGRESS, TicketStatus.INVALIDATED],
    }

    # Valid Project Status Transitions
    PROJECT_TRANSITIONS = {
        ProjectStatus.IN_PROGRESS: [ProjectStatus.PAUSED, ProjectStatus.COMPLETE],
        ProjectStatus.PAUSED: [ProjectStatus.IN_PROGRESS],
        ProjectStatus.COMPLETE: [],  # Terminal
    }

    def __init__(self, project_root=None, definition=None):
        self.project_root = Path(project_root or Path.cwd()).resolve()
        resolved = definition or resolve_definition(self.project_root)
        self.definition = resolved
        # Compatibility views derived from the definition, never hardcoded stage
        # data. Runtime methods re-resolve from the state so a recorded or
        # project-owned definition wins over this construction-time view.
        self.PLANNING_STAGE_TRANSITIONS = resolved.planning_transitions()
        self.GATE_VERDICTS = {
            stage_id: [GateVerdict(value) for value in resolved.gate_verdicts(stage_id)]
            for stage_id in resolved.ids if resolved.kind(stage_id) == "planning"
        }
        self.STAGE_ORDER = list(resolved.ids)

    # ============================================================
    # PLANNING STAGE TRANSITIONS
    # ============================================================

    def advance_planning_stage(self, state: Dict, gate_verdict: GateVerdict) -> TransitionResult:
        """Advance a planning stage using the stage's definition entry."""
        try:
            definition = definition_for_state(self.project_root, state)
            stage_id = state["pipeline_stage"]
            if not definition.is_planning(stage_id):
                return TransitionResult(False, error=f"Stage {stage_id} is not a planning stage")
            allowed = [GateVerdict(value) for value in definition.gate_verdicts(stage_id)]
        except PipelineDefinitionError as exc:
            return TransitionResult(False, error=str(exc))

        current_status = StageStatus(state["stage_status"])

        if state["project_status"] != "IN_PROGRESS":
            return TransitionResult(False, error="Project is not in progress")
        # Only allow gate when stage_status is READY_FOR_GATE
        if current_status != StageStatus.READY_FOR_GATE:
            return TransitionResult(False, error=f"Stage {stage_id} not ready for gate (status: {current_status.value})")

        # Validate verdict against this stage's declared gate types
        if gate_verdict not in allowed:
            return TransitionResult(False, error=f"Invalid verdict {gate_verdict.value} for stage {stage_id}")

        if gate_verdict == GateVerdict.PASS:
            config = definition.gate_receipt(stage_id)
            if config is not None:
                from gate_receipt import verify_gate_receipt
                evidence_errors = verify_gate_receipt(self.project_root, config)
                if evidence_errors:
                    return TransitionResult(False, error="Gate evidence rejected: " + "; ".join(evidence_errors))
            next_stage = definition.next_stage(stage_id)
            if next_stage is None:
                return TransitionResult(False, error=f"No next stage after {stage_id}")

            # Definition-driven gate hooks (e.g. ticket dependency validation
            # and T-009 conditional-stage guard); a string hook stays accepted.
            hooks = definition.gate_hooks(stage_id)
            if "validate_ticket_dependencies" in hooks:
                dep_errors = self._validate_ticket_dependencies(state)
                if dep_errors:
                    return TransitionResult(False, error="; ".join(dep_errors))
            if "require_conditional_gates" in hooks:
                gate_errors = self._conditional_gate_errors(state, definition, stage_id)
                if gate_errors:
                    return TransitionResult(False, error="; ".join(gate_errors))

            new_state = self._deep_copy_state(state)
            new_state["pipeline_stage"] = next_stage
            new_state["stage_status"] = StageStatus.IN_PROGRESS.value
            # Gate history: one entry per PASSed planning stage; the T-009
            # guard reads it, older states without it keep working unchanged.
            new_state.setdefault("stage_gates", {})[stage_id] = "PASS"

            # Definition-driven entry hook (e.g. start the first ready ticket).
            if definition.hook(next_stage, "on_enter") == "start_first_ticket":
                from dependency_scheduler import DependencyScheduler
                scheduler = DependencyScheduler(self.project_root)
                first_todo = scheduler.get_next_ticket(new_state, scheduler.load_ticket_files())
                if first_todo:
                    new_state["tickets"][first_todo]["status"] = TicketStatus.IN_PROGRESS.value
                    new_state["active_ticket_id"] = first_todo
                else:
                    new_state["active_ticket_id"] = None
            else:
                new_state["active_ticket_id"] = None  # Must be null outside ticket work

            return TransitionResult(True, new_state)

        elif gate_verdict == GateVerdict.FIX_REQUIRED:
            # Stay in same stage, status back to IN_PROGRESS
            new_state = self._deep_copy_state(state)
            new_state["stage_status"] = StageStatus.IN_PROGRESS.value
            return TransitionResult(True, new_state)

        elif gate_verdict == GateVerdict.USER_DECISION_REQUIRED:
            # Pause project - caller must provide decision_ref
            return TransitionResult(False, error="USER_DECISION_REQUIRED requires pause_project call with decision_ref")

        return TransitionResult(False, error=f"Unhandled verdict: {gate_verdict}")

    def _validate_ticket_dependencies(self, state: Dict) -> List[str]:
        """Validate all ticket dependencies are satisfied before entering IMPLEMENTATION."""
        from dependency_scheduler import DependencyScheduler
        
        scheduler = DependencyScheduler(self.project_root)
        ticket_files = scheduler.load_ticket_files()
        
        if not ticket_files:
            return ["No ticket files found in .harness/tickets/"]
        
        errors = scheduler.validate_dependencies(ticket_files)
        
        # Check that all tickets in state have corresponding ticket files
        state_tickets = set(state.get("tickets", {}).keys())
        file_tickets = set(ticket_files.keys())
        
        missing_in_files = state_tickets - file_tickets
        if missing_in_files:
            errors.append(f"Tickets in state but not in .harness/tickets/: {', '.join(sorted(missing_in_files))}")
        
        return errors

    def _conditional_gate_errors(self, state, definition, stage_id):
        """T-009 hook: every active conditional stage must have a recorded PASS.

        A conditional stage whose kernel-evaluated condition is active may not
        be skipped by any state that reaches this gate: init landing past a
        DESIGN stage, or a stage history missing its PASS, refuses the gate and
        names the stage and condition. The stage whose gate is passing right
        now is exempt from its own history (it is being recorded here).
        """
        from pipeline_definition import CONDITION_KEYS
        errors = []
        gates = state.get("stage_gates") or {}
        for stage in definition.stages:
            other_id = stage["id"]
            if other_id == stage_id or not definition.is_conditional(other_id):
                continue
            condition = stage.get("condition")
            if condition not in CONDITION_KEYS:
                continue
            if not self._condition_active(condition):
                continue
            if gates.get(other_id) != "PASS":
                errors.append(
                    f"Conditional stage {other_id} is active (condition {condition}) "
                    f"but has no recorded gate PASS; the {stage_id} gate refuses "
                    f"until {other_id} passes its own gate")
            elif definition.gate_receipt(other_id) is not None:
                from gate_receipt import verify_gate_receipt
                problems = verify_gate_receipt(self.project_root, definition.gate_receipt(other_id))
                if problems:
                    errors.append(f"Conditional stage {other_id} evidence is stale or invalid: " + "; ".join(problems))
        return errors

    def _condition_active(self, condition):
        """Evaluate one kernel-owned condition key against project data."""
        if condition != "golden_path_declares_collector":
            return False
        golden_path = self.project_root / ".harness" / "golden_path.json"
        try:
            data = json.loads(golden_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        steps = data.get("steps", []) if isinstance(data, dict) else []
        return any(isinstance(step, dict) and step.get("verification_type") == "collector"
            for step in steps)

    def set_stage_ready_for_gate(self, state: Dict) -> TransitionResult:
        """Mark a definition-declared planning stage as ready for gate."""
        if state["project_status"] != "IN_PROGRESS":
            return TransitionResult(False, error="Project is not in progress")
        current_stage = state["pipeline_stage"]
        try:
            definition = definition_for_state(self.project_root, state)
            if not definition.is_planning(current_stage):
                return TransitionResult(False, error=f"Stage {current_stage} is not a planning stage")
        except PipelineDefinitionError as exc:
            return TransitionResult(False, error=str(exc))

        if state["stage_status"] != StageStatus.IN_PROGRESS.value:
            return TransitionResult(False, error=f"Stage {current_stage} already {state['stage_status']}")

        new_state = state.copy()
        new_state["stage_status"] = StageStatus.READY_FOR_GATE.value
        return TransitionResult(True, new_state)

    # ============================================================
    # TICKET TRANSITIONS (IMPLEMENTATION/REVIEW stages)
    # ============================================================

    def start_ticket(self, state: Dict, ticket_id: str) -> TransitionResult:
        """Start a ticket (TODO -> IN_PROGRESS)."""
        # Validate project state
        try:
            definition = definition_for_state(self.project_root, state)
            if not definition.is_execution(state["pipeline_stage"]):
                return TransitionResult(False, error=f"Cannot start ticket in stage {state['pipeline_stage']}")
        except PipelineDefinitionError as exc:
            return TransitionResult(False, error=str(exc))

        if state["project_status"] != ProjectStatus.IN_PROGRESS.value:
            return TransitionResult(False, error=f"Project not in progress: {state['project_status']}")

        if state["project_status"] != "IN_PROGRESS":
            return TransitionResult(False, error="Project is not in progress")
        tickets = state.get("tickets", {})
        if ticket_id not in tickets:
            return TransitionResult(False, error=f"Ticket {ticket_id} not found")

        ticket = tickets[ticket_id]
        current_status = TicketStatus(ticket["status"])

        # Check valid transition
        if TicketStatus.IN_PROGRESS not in self.TICKET_TRANSITIONS.get(current_status, []):
            return TransitionResult(False, error=f"Cannot start ticket from {current_status.value}")

        # Check dependencies (all dependencies must be COMPLETE)
        # This requires ticket files - for now we check state only
        # Full implementation would read .harness/tickets/T-<NNN>.md

        # Check no other active ticket
        if state.get("active_ticket_id") and state["active_ticket_id"] != ticket_id:
            return TransitionResult(False, error=f"Another ticket {state['active_ticket_id']} is active")

        new_state = self._deep_copy_state(state)
        new_state["tickets"][ticket_id]["status"] = TicketStatus.IN_PROGRESS.value
        new_state["active_ticket_id"] = ticket_id
        new_state["stage_status"] = StageStatus.IN_PROGRESS.value
        return TransitionResult(True, new_state)

    def mark_ticket_ready_for_review(self, state: Dict, ticket_id: str) -> TransitionResult:
        """Mark ticket as READY_FOR_REVIEW (IN_PROGRESS -> READY_FOR_REVIEW)."""
        if state["project_status"] != "IN_PROGRESS":
            return TransitionResult(False, error="Project is not in progress")
        tickets = state.get("tickets", {})
        if ticket_id not in tickets:
            return TransitionResult(False, error=f"Ticket {ticket_id} not found")

        if state.get("active_ticket_id") != ticket_id:
            return TransitionResult(False, error=f"Ticket {ticket_id} is not active")

        ticket = tickets[ticket_id]
        current_status = TicketStatus(ticket["status"])

        if TicketStatus.READY_FOR_REVIEW not in self.TICKET_TRANSITIONS.get(current_status, []):
            return TransitionResult(False, error=f"Cannot mark ready for review from {current_status.value}")

        new_state = self._deep_copy_state(state)
        new_state["tickets"][ticket_id]["status"] = TicketStatus.READY_FOR_REVIEW.value
        return TransitionResult(True, new_state)

    def complete_ticket_via_review(self, state: Dict, ticket_id: str) -> TransitionResult:
        """
        Complete a ticket via Review PASS.
        DEVELOPER CANNOT CALL THIS DIRECTLY - only via review verdict PASS.
        """
        return TransitionResult(False, error="Completion requires Workflow review evidence")

    def invalidate_ticket(self, state: Dict, ticket_id: str) -> TransitionResult:
        """Invalidate a ticket (any -> INVALIDATED)."""
        if state["project_status"] != "IN_PROGRESS":
            return TransitionResult(False, error="Project is not in progress")
        tickets = state.get("tickets", {})
        if ticket_id not in tickets:
            return TransitionResult(False, error=f"Ticket {ticket_id} not found")

        ticket = tickets[ticket_id]
        current_status = TicketStatus(ticket["status"])

        if TicketStatus.INVALIDATED not in self.TICKET_TRANSITIONS.get(current_status, []):
            return TransitionResult(False, error=f"Cannot invalidate ticket from {current_status.value}")

        new_state = self._deep_copy_state(state)
        new_state["tickets"][ticket_id]["status"] = TicketStatus.INVALIDATED.value
        if state.get("active_ticket_id") == ticket_id:
            new_state["active_ticket_id"] = None
        return TransitionResult(True, new_state)

    def pause_ticket(self, state: Dict, ticket_id: str) -> TransitionResult:
        """Pause a ticket (IN_PROGRESS/READY_FOR_REVIEW -> PAUSED)."""
        if state["project_status"] != "IN_PROGRESS":
            return TransitionResult(False, error="Project is not in progress")
        tickets = state.get("tickets", {})
        if ticket_id not in tickets:
            return TransitionResult(False, error=f"Ticket {ticket_id} not found")

        ticket = tickets[ticket_id]
        current_status = TicketStatus(ticket["status"])

        if TicketStatus.PAUSED not in self.TICKET_TRANSITIONS.get(current_status, []):
            return TransitionResult(False, error=f"Cannot pause ticket from {current_status.value}")

        new_state = self._deep_copy_state(state)
        new_state["tickets"][ticket_id]["status"] = TicketStatus.PAUSED.value
        if state.get("active_ticket_id") == ticket_id:
            new_state["active_ticket_id"] = None
        return TransitionResult(True, new_state)

    def resume_ticket(self, state: Dict, ticket_id: str) -> TransitionResult:
        """Resume a paused ticket (PAUSED -> IN_PROGRESS)."""
        if state["project_status"] != "IN_PROGRESS":
            return TransitionResult(False, error="Project is not in progress")
        tickets = state.get("tickets", {})
        if ticket_id not in tickets:
            return TransitionResult(False, error=f"Ticket {ticket_id} not found")

        ticket = tickets[ticket_id]
        current_status = TicketStatus(ticket["status"])

        if TicketStatus.IN_PROGRESS not in self.TICKET_TRANSITIONS.get(current_status, []):
            return TransitionResult(False, error=f"Cannot resume ticket from {current_status.value}")

        if state.get("active_ticket_id"):
            return TransitionResult(False, error=f"Another ticket {state['active_ticket_id']} is active")

        new_state = self._deep_copy_state(state)
        new_state["tickets"][ticket_id]["status"] = TicketStatus.IN_PROGRESS.value
        new_state["active_ticket_id"] = ticket_id
        return TransitionResult(True, new_state)

    # ============================================================
    # REVIEW VERDICT PROCESSING
    # ============================================================

    def process_review_verdict(self, state: Dict, ticket_id: str, verdict: ReviewVerdict) -> TransitionResult:
        """Process review verdict and update state accordingly."""
        if state["project_status"] != "IN_PROGRESS":
            return TransitionResult(False, error="Project is not in progress")
        tickets = state.get("tickets", {})
        if ticket_id not in tickets:
            return TransitionResult(False, error=f"Ticket {ticket_id} not found")

        if state.get("active_ticket_id") != ticket_id:
            return TransitionResult(False, error=f"Ticket {ticket_id} is not active")

        ticket = tickets[ticket_id]
        if ticket["status"] != TicketStatus.READY_FOR_REVIEW.value:
            return TransitionResult(False, error=f"Ticket {ticket_id} not ready for review (status: {ticket['status']})")

        if verdict == ReviewVerdict.PASS:
            return TransitionResult(False, error="Completion requires Workflow review evidence")

        elif verdict == ReviewVerdict.FIX_REQUIRED:
            # Increment review_attempts, move back to IN_PROGRESS
            new_state = self._deep_copy_state(state)
            new_state["tickets"][ticket_id]["review_attempts"] += 1
            new_state["tickets"][ticket_id]["status"] = TicketStatus.IN_PROGRESS.value
            attempts = new_state["tickets"][ticket_id]["review_attempts"]

            # Build fix loop memory for the next implementation attempt
            fix_memory = self._build_fix_loop_memory(new_state, ticket_id, attempts)
            new_state["tickets"][ticket_id]["fix_loop_memory"] = fix_memory

            # Auto-pause at 3 attempts
            if attempts >= new_state["tickets"][ticket_id].get("retry_limit", 3):
                new_state["project_status"] = ProjectStatus.PAUSED.value
                ticket_num = ''.join(filter(str.isdigit, ticket_id))
                new_state["pause"] = {
                    "reason": PauseReason.RETRY_LIMIT_REACHED.value,
                    "decision_ref": f"DEC-{ticket_num.zfill(3)}"
                }

            return TransitionResult(True, new_state)

        elif verdict == ReviewVerdict.USER_DECISION_REQUIRED:
            # Pause project - caller provides decision_ref
            return TransitionResult(False, error="USER_DECISION_REQUIRED requires pause_project call")

        return TransitionResult(False, error=f"Unknown verdict: {verdict}")

    # ============================================================
    # GATE VERDICT PROCESSING (for planning stages)
    # ============================================================

    def process_gate_verdict(self, state: Dict, verdict: GateVerdict, decision_ref: Optional[str] = None) -> TransitionResult:
        """Process gate verdict for a definition-declared planning stage."""
        try:
            definition = definition_for_state(self.project_root, state)
            stage_id = state["pipeline_stage"]
            if not definition.is_planning(stage_id):
                return TransitionResult(False, error=f"Gate verdict not applicable in stage {stage_id}")
            allowed = [GateVerdict(value) for value in definition.gate_verdicts(stage_id)]
        except PipelineDefinitionError as exc:
            return TransitionResult(False, error=str(exc))

        if state["stage_status"] != StageStatus.READY_FOR_GATE.value:
            return TransitionResult(False, error=f"Stage not ready for gate: {state['stage_status']}")

        if verdict not in allowed:
            return TransitionResult(False, error=f"Invalid verdict {verdict.value} for stage {stage_id}")

        if verdict == GateVerdict.PASS:
            return self.advance_planning_stage(state, verdict)

        elif verdict == GateVerdict.FIX_REQUIRED:
            new_state = self._deep_copy_state(state)
            new_state["stage_status"] = StageStatus.IN_PROGRESS.value
            return TransitionResult(True, new_state)

        elif verdict == GateVerdict.USER_DECISION_REQUIRED:
            if not decision_ref:
                return TransitionResult(False, error="USER_DECISION_REQUIRED requires decision_ref")
            new_state = self._deep_copy_state(state)
            new_state["project_status"] = ProjectStatus.PAUSED.value
            new_state["pause"] = {
                "reason": PauseReason.GATE_USER_DECISION_REQUIRED.value,
                "decision_ref": decision_ref
            }
            return TransitionResult(True, new_state)

        return TransitionResult(False, error=f"Unknown gate verdict: {verdict}")

    # ============================================================
    # PROJECT PAUSE/RESUME
    # ============================================================

    def pause_project(self, state: Dict, reason: PauseReason, decision_ref: str) -> TransitionResult:
        """Pause the project and create DEC artifact."""
        if state["project_status"] == ProjectStatus.PAUSED.value:
            return TransitionResult(False, error="Project already paused")

        if state["project_status"] == ProjectStatus.COMPLETE.value:
            return TransitionResult(False, error="Cannot pause completed project")

        # Validate reason
        try:
            PauseReason(reason)
        except ValueError:
            return TransitionResult(False, error=f"Invalid pause reason: {reason}")

        # Validate decision_ref format
        if not decision_ref or not decision_ref.startswith("DEC-"):
            return TransitionResult(False, error="Invalid decision_ref format (must be DEC-<NNN>)")

        new_state = self._deep_copy_state(state)
        new_state["project_status"] = ProjectStatus.PAUSED.value
        new_state["pause"] = {
            "reason": reason.value if isinstance(reason, PauseReason) else reason,
            "decision_ref": decision_ref
        }
        
        return TransitionResult(True, new_state)

    def resume_project(self, state: Dict) -> TransitionResult:
        return TransitionResult(False, error="Resume requires Workflow decision validation")

    # ============================================================
    # FINDING TRANSITIONS
    # ============================================================

    def add_finding(self, state: Dict, finding_id: str, finding_data: Dict) -> TransitionResult:
        """Add a new finding."""
        # Validate finding_key format
        finding_key = finding_data.get("finding_key", "")
        if not finding_key or not all(c.islower() or c.isdigit() or c == '-' for c in finding_key):
            return TransitionResult(False, error=f"Invalid finding_key format: {finding_key}")

        # Check ticket exists
        ticket_id = finding_data.get("ticket_id")
        if not ticket_id or ticket_id not in state.get("tickets", {}):
            return TransitionResult(False, error=f"Ticket {ticket_id} not found")

        new_state = self._deep_copy_state(state)
        new_state["findings"][finding_id] = finding_data

        # Add to ticket's active_findings
        if finding_id not in new_state["tickets"][ticket_id]["active_findings"]:
            new_state["tickets"][ticket_id]["active_findings"].append(finding_id)

        return TransitionResult(True, new_state)

    def update_finding_status(self, state: Dict, finding_id: str, new_status: FindingStatus) -> TransitionResult:
        """Update finding status (OPEN -> RESOLVED, RESOLVED -> REOPENED)."""
        if finding_id not in state.get("findings", {}):
            return TransitionResult(False, error=f"Finding {finding_id} not found")

        finding = state["findings"][finding_id]
        current_status = FindingStatus(finding["status"])

        # Valid transitions
        valid_transitions = {
            FindingStatus.OPEN: [FindingStatus.RESOLVED],
            FindingStatus.RESOLVED: [FindingStatus.REOPENED],
            FindingStatus.REOPENED: [FindingStatus.RESOLVED],
        }

        if new_status not in valid_transitions.get(current_status, []):
            return TransitionResult(False, error=f"Invalid finding transition: {current_status.value} -> {new_status.value}")

        new_state = self._deep_copy_state(state)
        new_state["findings"][finding_id]["status"] = new_status.value

        # Update ticket's active_findings
        ticket_id = finding.get("ticket_id")
        if ticket_id and ticket_id in new_state["tickets"]:
            active = new_state["tickets"][ticket_id]["active_findings"]
            if new_status == FindingStatus.RESOLVED:
                if finding_id in active:
                    active.remove(finding_id)
            elif new_status == FindingStatus.REOPENED:
                if finding_id not in active:
                    active.append(finding_id)
                # Update last_seen_attempt
                ticket = new_state["tickets"][ticket_id]
                new_state["findings"][finding_id]["last_seen_attempt"] = ticket["review_attempts"]
                new_state["findings"][finding_id]["reopen_count"] += 1

        return TransitionResult(True, new_state)

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _deep_copy_state(self, state: Dict) -> Dict:
        """Create a deep copy of state."""
        return json.loads(json.dumps(state))

    def _build_fix_loop_memory(self, state: Dict, ticket_id: str, attempt_number: int) -> Dict:
        """
        Build fix loop memory for the next implementation attempt.
        
        Includes:
        - Active findings for this ticket (with finding_key for continuity)
        - Previous fix summary (from last review's criteria evidence)
        - Failure reasons (from FAIL/UNVERIFIED criteria)
        - Does NOT load full review history
        - Uses finding_key for finding continuity across attempts
        """
        ticket = state["tickets"].get(ticket_id, {})
        findings = state.get("findings", {})
        
        # Get active findings for this ticket
        active_finding_ids = ticket.get("active_findings", [])
        active_findings = []
        for fid in active_finding_ids:
            if fid in findings:
                finding = findings[fid]
                active_findings.append({
                    "finding_id": fid,
                    "finding_key": finding.get("finding_key"),
                    "criterion_ref": finding.get("criterion_ref"),
                    "description": finding.get("description"),
                    "blocking": finding.get("blocking", True),
                    "status": finding.get("status"),
                    "first_detected_attempt": finding.get("first_detected_attempt"),
                    "last_seen_attempt": finding.get("last_seen_attempt"),
                    "reopen_count": finding.get("reopen_count", 0)
                })
        
        # Get previous attempt's failure info from ticket's fix_loop_memory if exists
        previous_memory = ticket.get("fix_loop_memory", {})
        # Check both fix_summary (from update_fix_loop_memory) and previous_fix_summary (from previous attempt's memory)
        previous_fix_summary = previous_memory.get("fix_summary") or previous_memory.get("previous_fix_summary", "")
        previous_failure_reasons = previous_memory.get("failure_reasons") or previous_memory.get("previous_failure_reasons", [])
        
        # Build failure reasons from current active findings (these are what caused FIX_REQUIRED)
        failure_reasons = []
        for af in active_findings:
            if af.get("blocking", True):
                failure_reasons.append({
                    "finding_key": af["finding_key"],
                    "criterion_ref": af["criterion_ref"],
                    "description": af["description"]
                })
        
        return {
            "attempt_number": attempt_number,
            "active_findings": active_findings,
            "active_finding_keys": [af["finding_key"] for af in active_findings],
            "failure_reasons": failure_reasons,
            "previous_fix_summary": previous_fix_summary,
            "previous_failure_reasons": previous_failure_reasons,
            "total_findings_count": len(active_findings),
            "blocking_findings_count": len([af for af in active_findings if af.get("blocking", True)])
        }

    def get_fix_loop_memory(self, state: Dict, ticket_id: str) -> Optional[Dict]:
        """Get fix loop memory for a ticket (for Implementation agent)."""
        ticket = state.get("tickets", {}).get(ticket_id)
        if not ticket:
            return None
        return ticket.get("fix_loop_memory")

    def update_fix_loop_memory(self, state: Dict, ticket_id: str, fix_summary: str) -> TransitionResult:
        """Update fix loop memory with the fix summary from Implementation."""
        if ticket_id not in state.get("tickets", {}):
            return TransitionResult(False, error=f"Ticket {ticket_id} not found")
        
        new_state = self._deep_copy_state(state)
        if "fix_loop_memory" not in new_state["tickets"][ticket_id]:
            new_state["tickets"][ticket_id]["fix_loop_memory"] = {}
        new_state["tickets"][ticket_id]["fix_loop_memory"]["fix_summary"] = fix_summary
        return TransitionResult(True, new_state)

    def validate_transition(self, from_state: Dict, to_state: Dict) -> Tuple[bool, Optional[str]]:
        """Validate that a transition is allowed (for testing/verification)."""
        # This is a post-hoc validation - checks if from_state -> to_state is valid
        # In practice, the engine methods above should be used to create transitions
        return False, "Generic transition validation is unsupported; use named workflow operations"


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def create_initial_state(first_stage: str) -> Dict:
    """Create initial state for a new project.

    first_stage must be the resolved pipeline definition's entry stage (T-006);
    no stage name is assumed here.
    """
    return {
        "schema_version": "1.1",
        "project_status": ProjectStatus.IN_PROGRESS.value,
        "pipeline_stage": first_stage,
        "stage_status": StageStatus.IN_PROGRESS.value,
        "active_ticket_id": None,
        "pause": None,
        "tickets": {},
        "findings": {}
    }


def is_terminal_state(state: Dict) -> bool:
    """Check if project is in terminal state."""
    return state["project_status"] == ProjectStatus.COMPLETE.value


def get_next_actionable_tickets(state: Dict) -> List[str]:
    """Get tickets that can be started (all dependencies COMPLETE)."""
    tickets = state.get("tickets", {})
    actionable = []
    for tid, ticket in tickets.items():
        if ticket["status"] == TicketStatus.TODO.value:
            # Check dependencies - would need ticket files
            actionable.append(tid)
    return actionable


import json