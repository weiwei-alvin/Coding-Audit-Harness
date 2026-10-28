"""T-008 three-tier evidence: deterministic, captured, declared.

The positive case proves all three tiers can coexist in one review. Negative
cases prove declared evidence needs source + limitations, a declared tier cannot
be claimed without matching evidence, and a stage can require tiers in its
definition. Legacy review payloads without tier are rejected by the schema.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from payload_validator import PayloadValidator
from runner import HarnessRunner
from storage import source_hash
from workflow import Workflow

import test_support


def pipeline_definition(required_tiers):
    return {
        "schema_version": "0.1",
        "pipeline": "tiered-review",
        "stages": [
            dict(id="DISCOVERY", kind="planning", next="SPEC",
                gate_verdicts=["PASS", "FIX_REQUIRED", "USER_DECISION_REQUIRED"]),
            dict(id="SPEC", kind="planning", next="TICKETS",
                gate_verdicts=["PASS", "FIX_REQUIRED", "USER_DECISION_REQUIRED"]),
            dict(id="TICKETS", kind="planning", next="IMPLEMENTATION",
                gate_verdicts=["PASS", "FIX_REQUIRED", "USER_DECISION_REQUIRED"]),
            dict(id="IMPLEMENTATION", kind="execution", next="REVIEW",
                on_enter="start_first_ticket", required_evidence_tiers=required_tiers),
            dict(id="REVIEW", kind="execution", terminal=True),
        ],
    }


def prepare(root, required_tiers):
    state = test_support.fixture(root, count=1)
    (root / ".harness/pipeline.json").write_text(
        json.dumps(pipeline_definition(required_tiers)), encoding="utf-8")
    state.update(pipeline_stage="IMPLEMENTATION", stage_status="IN_PROGRESS", active_ticket_id="T-001")
    state["tickets"]["T-001"]["status"] = "IN_PROGRESS"
    (root / ".harness/state.json").write_text(json.dumps(state), encoding="utf-8")
    (root / "check.py").write_text('print("ok")\n', encoding="utf-8")
    (root / "collect.py").write_text(
        "from pathlib import Path\n"
        "Path('artifacts').mkdir(exist_ok=True)\n"
        "Path('artifacts/report.txt').write_text('captured-evidence\\n', encoding='utf-8')\n",
        encoding="utf-8")
    steps = [
        dict(id="GP-001", description="addition", user_story_ids=["US-001"], ticket_ids=["T-001"],
            verification_command=[sys.executable, "check.py"], expected_output="ok"),
        dict(id="GP-002", description="captured report", user_story_ids=["US-001"], ticket_ids=["T-001"],
            verification_command=[sys.executable, "collect.py"], expected_output="",
            verification_type="collector", expected_artifacts=["artifacts/report.txt"]),
    ]
    (root / ".harness/golden_path.json").write_text(
        json.dumps({"steps": steps, "source_hash_exclude": ["artifacts"]}), encoding="utf-8")
    return state


def receipt(root):
    return Workflow(HarnessRunner(root), trusted=True, confirm_pass=lambda *_: True).verify("T-001")


def mark_ready(root):
    path = root / ".harness/state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state["tickets"]["T-001"]["status"] = "READY_FOR_REVIEW"
    path.write_text(json.dumps(state), encoding="utf-8")


def failing_review(root, verdict, decision_context=None):
    """A review that rejects the ticket; no successful receipt exists by design."""
    data = dict(ticket_id="T-001", review_round=1, source_hash=source_hash(root),
        verdict=verdict,
        criteria=[dict(id="GP-001", status="FAIL", critical=True,
            tier="deterministic", evidence="the assertion failed")],
        findings=[])
    if verdict == "FIX_REQUIRED":
        data["findings"] = [dict(finding_key="wrong-addition", criterion_ref="GP-001",
            description="The addition is wrong", blocking=True)]
    if decision_context is not None:
        data["decision_context"] = decision_context
    folder = root / ".harness/inbox"
    folder.mkdir(exist_ok=True)
    path = folder / "review-fail.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def payloads(root, evidence, include_declared=True, declared_source="Operator review",
             declared_limitations="One Windows environment only"):
    common = dict(ticket_id="T-001", review_round=evidence["review_round"],
        source_hash=evidence["source_hash"], verification_id=evidence["verification_id"])
    criteria = [
        dict(id="GP-001", status="PASS", critical=True, tier="deterministic"),
        dict(id="GP-002", status="PASS", critical=True, tier="captured"),
    ]
    if include_declared:
        criteria.append(dict(id="MANUAL-1", status="PASS", critical=True, tier="declared",
            source=declared_source, limitations=declared_limitations))
    review = dict(**common, verdict="PASS", criteria=criteria, findings=[])
    handoff = dict(**common,
        changes=[dict(file="calc.py", summary="addition and captured report")],
        verification=[dict(step="GP-001", expected="exit 0", actual="exit 0", status="PASS")],
        dependencies=[])
    folder = root / ".harness/inbox"
    folder.mkdir(exist_ok=True)
    review_path = folder / "review.json"
    handoff_path = folder / "handoff.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
    return review_path, handoff_path


class ThreeTierReviewTests(unittest.TestCase):
    def test_deterministic_captured_and_declared_review_pass(self):
        with tempfile.TemporaryDirectory(prefix="harness-tiers-") as tmp:
            root = Path(tmp)
            prepare(root, ["deterministic", "captured", "declared"])
            evidence = receipt(root)
            self.assertEqual(evidence["evidence_tiers"], ["captured", "deterministic"])
            mark_ready(root)
            review_path, handoff_path = payloads(root, evidence)
            workflow = Workflow(HarnessRunner(root), trusted=True, confirm_pass=lambda *_: True)
            workflow.review("T-001", "PASS", review_path, handoff_path)
            state = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
            review_ref = state["tickets"]["T-001"]["review_history"][0]
            stored = workflow.read_artifact(review_ref)
        self.assertEqual(state["project_status"], "COMPLETE")
        self.assertEqual(state["pipeline_stage"], "REVIEW")
        self.assertIn("final_verification", state)
        self.assertEqual([x["tier"] for x in stored["review"]["criteria"]],
            ["deterministic", "captured", "declared"])

    def test_declared_without_source_or_limitations_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="harness-tiers-") as tmp:
            root = Path(tmp)
            prepare(root, ["deterministic", "captured", "declared"])
            evidence = receipt(root)
            mark_ready(root)
            workflow = Workflow(HarnessRunner(root), trusted=True, confirm_pass=lambda *_: True)
            for field in ("source", "limitations"):
                with self.subTest(field=field):
                    review_path, handoff_path = payloads(root, evidence,
                        declared_source="   " if field == "source" else "Operator review",
                        declared_limitations="   " if field == "limitations" else "One environment")
                    before = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
                    with self.assertRaisesRegex(ValueError, "requires nonblank source and limitations"):
                        workflow.review("T-001", "PASS", review_path, handoff_path)
                    after = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
                    self.assertEqual(after, before)

    def test_stage_required_tier_missing_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="harness-tiers-") as tmp:
            root = Path(tmp)
            prepare(root, ["deterministic", "captured", "declared"])
            evidence = receipt(root)
            mark_ready(root)
            review_path, handoff_path = payloads(root, evidence, include_declared=False)
            before = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
            with self.assertRaisesRegex(ValueError, r"requires evidence tiers.*missing \['declared'\]"):
                Workflow(HarnessRunner(root), trusted=True, confirm_pass=lambda *_: True).review("T-001", "PASS", review_path, handoff_path)
            after = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(after, before)

    def test_deterministic_claim_without_matching_step_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="harness-tiers-") as tmp:
            root = Path(tmp)
            prepare(root, ["deterministic", "captured", "declared"])
            evidence = receipt(root)
            mark_ready(root)
            review_path, handoff_path = payloads(root, evidence)
            data = json.loads(review_path.read_text(encoding="utf-8"))
            data["criteria"].append(dict(id="MANUAL-DET", status="PASS", critical=True,
                tier="deterministic"))
            review_path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no matching verification step"):
                Workflow(HarnessRunner(root), trusted=True, confirm_pass=lambda *_: True).review("T-001", "PASS", review_path, handoff_path)

    def test_tiered_stage_still_accepts_fix_required_without_receipt(self):
        with tempfile.TemporaryDirectory(prefix="harness-tiers-") as tmp:
            root = Path(tmp)
            prepare(root, ["deterministic", "captured", "declared"])
            mark_ready(root)
            before = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
            review_path = failing_review(root, "FIX_REQUIRED")
            Workflow(HarnessRunner(root), trusted=True, confirm_pass=lambda *_: True).review(
                "T-001", "FIX_REQUIRED", review_path, None)
            after = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(after["project_status"], "IN_PROGRESS")
        self.assertEqual(after["tickets"]["T-001"]["status"], "IN_PROGRESS")
        self.assertEqual(after["tickets"]["T-001"]["review_attempts"],
            before["tickets"]["T-001"]["review_attempts"] + 1)

    def test_tiered_stage_still_accepts_user_decision_required(self):
        with tempfile.TemporaryDirectory(prefix="harness-tiers-") as tmp:
            root = Path(tmp)
            prepare(root, ["deterministic", "captured", "declared"])
            mark_ready(root)
            review_path = failing_review(root, "USER_DECISION_REQUIRED", {
                "question": "Should the addition semantics change?",
                "why_blocked": "The current SPEC does not define negative operands.",
                "options": [{"label": "FIX_REQUIRED",
                    "impact": "Return to the ticket and clarify the intended behavior."}],
            })
            Workflow(HarnessRunner(root), trusted=True, confirm_pass=lambda *_: True).review(
                "T-001", "USER_DECISION_REQUIRED", review_path, None)
            state = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["project_status"], "PAUSED")
        self.assertEqual(state["pause"]["reason"], "REVIEW_USER_DECISION_REQUIRED")

    def test_legacy_review_payload_without_tier_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="harness-tiers-") as tmp:
            root = Path(tmp)
            prepare(root, [])
            valid, errors = PayloadValidator(root).validate("review", {
                "ticket_id": "T-001", "verdict": "PASS",
                "criteria": [{"id": "GP-001", "status": "PASS", "critical": True}],
                "findings": []})
        self.assertFalse(valid)
        self.assertTrue(any("tier" in error and "required" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
