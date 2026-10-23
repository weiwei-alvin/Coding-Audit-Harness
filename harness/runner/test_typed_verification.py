"""T-007 typed verification and artifact receipts.

Assertion steps keep their old shape. Collector steps declare expected artifacts;
the receipt records each existing artifact's relative path and SHA-256, and a
missing artifact fails verification (CLI exit != 0). Every project is disposable.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from golden_path_verifier import GoldenPathVerifier
from runner import HarnessRunner
from schema_validation import validator
from workflow import Workflow

import test_support


def prepare(root, steps, exclude=None):
    state = test_support.fixture(root, count=1)
    state.update(pipeline_stage="IMPLEMENTATION", stage_status="IN_PROGRESS", active_ticket_id="T-001")
    state["tickets"]["T-001"]["status"] = "IN_PROGRESS"
    (root / ".harness/state.json").write_text(json.dumps(state), encoding="utf-8")
    payload = {"steps": steps}
    if exclude is not None:
        payload["source_hash_exclude"] = exclude
    (root / ".harness/golden_path.json").write_text(json.dumps(payload), encoding="utf-8")
    return state


def write_scripts(root):
    (root / "check.py").write_text('print("ok")\n', encoding="utf-8")
    (root / "collect.py").write_text(
        "from pathlib import Path\n"
        "Path('artifacts').mkdir(exist_ok=True)\n"
        "Path('artifacts/report.txt').write_text('captured-evidence\\n', encoding='utf-8')\n",
        encoding="utf-8")


def assertion_step(**extra):
    step = dict(id="GP-001", description="addition", user_story_ids=["US-001"], ticket_ids=["T-001"],
        verification_command=[sys.executable, "check.py"], expected_output="ok")
    step.update(extra)
    return step


def collector_step(**extra):
    step = dict(id="GP-002", description="captured report", user_story_ids=["US-001"], ticket_ids=["T-001"],
        verification_command=[sys.executable, "collect.py"], expected_output="",
        verification_type="collector", expected_artifacts=["artifacts/report.txt"])
    step.update(extra)
    return step


class TypedVerificationTests(unittest.TestCase):
    def test_old_assertion_step_keeps_behavior_and_gets_deterministic_tier(self):
        with tempfile.TemporaryDirectory(prefix="harness-typed-") as tmp:
            root = Path(tmp)
            prepare(root, [assertion_step()])
            write_scripts(root)
            evidence = Workflow(HarnessRunner(root), trusted=True).verify("T-001")
            self.assertTrue(evidence["all_passed"])
            self.assertEqual(evidence["results"][0]["status"], "PASSED")
            self.assertEqual(evidence["results"][0]["tier"], "deterministic")
            self.assertEqual(evidence["results"][0]["artifacts"], [])
            self.assertEqual(evidence["evidence_tiers"], ["deterministic"])
            validator(root / "harness", "verification-receipt.schema.json").validate(evidence)

    def test_collector_receipt_has_relative_path_and_sha256(self):
        with tempfile.TemporaryDirectory(prefix="harness-typed-") as tmp:
            root = Path(tmp)
            prepare(root, [collector_step()], exclude=["artifacts"])
            write_scripts(root)
            workflow = Workflow(HarnessRunner(root), trusted=True)
            evidence = workflow.verify("T-001")
            artifact = root / "artifacts/report.txt"
            expected_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
            # The generated artifact is excluded from the source snapshot, so a
            # second run is stable rather than a source change.
            again = workflow.verify("T-001")
        result = evidence["results"][0]
        self.assertTrue(evidence["all_passed"])
        self.assertEqual(result["tier"], "captured")
        self.assertEqual(result["artifacts"], [dict(path="artifacts/report.txt", sha256=expected_sha)])
        self.assertEqual(evidence["evidence_tiers"], ["captured"])
        self.assertTrue(again["all_passed"])
        self.assertEqual(again["results"][0]["artifacts"], result["artifacts"])

    def test_missing_artifact_fails_and_cli_exits_nonzero(self):
        with tempfile.TemporaryDirectory(prefix="harness-typed-") as tmp:
            root = Path(tmp)
            prepare(root, [collector_step(expected_artifacts=["artifacts/missing.txt"])], exclude=["artifacts"])
            write_scripts(root)
            completed = subprocess.run(
                [sys.executable, str(root / "harness/runner/runner.py"), "verify-ticket",
                 "--ticket", "T-001", "--trust-commands"],
                cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertNotEqual(completed.returncode, 0, completed.stdout)
            self.assertIn("Required verification FAIL", completed.stderr)
            state = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
            ref = state["tickets"]["T-001"]["verification"]
            receipt = json.loads((root / ".harness" / ref["path"]).read_text(encoding="utf-8"))
        self.assertFalse(receipt["all_passed"])
        self.assertEqual(receipt["results"][0]["status"], "FAILED")
        self.assertIn("Missing expected artifact", receipt["results"][0]["error"])
        self.assertEqual(receipt["results"][0]["artifacts"], [])

    def test_collector_without_exclusion_is_a_source_change(self):
        with tempfile.TemporaryDirectory(prefix="harness-typed-") as tmp:
            root = Path(tmp)
            prepare(root, [collector_step()])
            write_scripts(root)
            with self.assertRaisesRegex(ValueError, "Project changed during verification"):
                Workflow(HarnessRunner(root), trusted=True).verify("T-001")

    def test_invalid_collector_declarations_are_refused(self):
        cases = [
            (collector_step(expected_artifacts=[]), "must declare expected_artifacts"),
            (collector_step(expected_artifacts=["../escape.txt"]), "relative path"),
            (assertion_step(expected_artifacts=["report.txt"]), "only valid for collector"),
            (collector_step(verification_type="unknown"), "assertion or collector"),
        ]
        for step, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory(prefix="harness-typed-") as tmp:
                root = Path(tmp)
                prepare(root, [step])
                write_scripts(root)
                with self.assertRaisesRegex(ValueError, message):
                    GoldenPathVerifier(root)

    def test_receipt_schema_requires_tier_and_artifacts(self):
        legacy = dict(ticket_id="T-001", review_round=1, source_hash="0" * 64,
            verification_id="v", all_passed=True, evidence_tiers=[],
            results=[dict(step_id="GP-001", status="PASSED", stdout="", stderr="",
                returncode=0, error=None)])
        with tempfile.TemporaryDirectory(prefix="harness-typed-") as tmp:
            root = Path(tmp)
            test_support.fixture(root, count=1)
            receipt_validator = validator(root / "harness", "verification-receipt.schema.json")
            with self.assertRaises(Exception):
                receipt_validator.validate(legacy)


if __name__ == "__main__":
    unittest.main()
