"""Critical PASS terminal approval: fail closed, correct prefix, unchanged state.

All fixtures are disposable. Normal CLI never receives an approval-bypass option.
"""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from runner import HarnessRunner
from storage import plan_hash
from workflow import Workflow, InteractiveApprovalError, APPROVAL_EXIT_CODE
import test_support
from test_evidence_tiers import prepare, receipt, mark_ready, payloads


class FakeTTY(io.StringIO):
    def isatty(self):
        return True


class TerminalApprovalTests(unittest.TestCase):
    def gate_fixture(self, root):
        test_support.fixture(root, count=1)
        (root / ".harness/golden_path.json").write_text(
            json.dumps({"steps": [dict(
                id="GP-001", description="add numbers", user_story_ids=["US-001"],
                ticket_ids=["T-001"], verification_command=[sys.executable, "-c", "assert 2+3==5"],
                expected_output="")]}), encoding="utf-8")
        return Workflow(HarnessRunner(root))

    def review_fixture(self, root):
        prepare(root, [])
        evidence = receipt(root)
        mark_ready(root)
        review, handoff = payloads(root, evidence, include_declared=False)
        return Workflow(HarnessRunner(root), trusted=True), review, handoff

    def test_gate_refuses_non_tty_without_changing_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workflow = self.gate_fixture(root)
            state_file = root / ".harness/state.json"
            before = state_file.read_bytes()
            with patch("workflow.sys.stdin", io.StringIO("")):
                with self.assertRaisesRegex(InteractiveApprovalError, "TTY_CONFIRMATION_REQUIRED"):
                    workflow.gate("PASS")
            self.assertEqual(before, state_file.read_bytes())
            self.assertNotIn("approved_plan", json.loads(before))

    def test_gate_wrong_prefix_refused_and_correct_prefix_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workflow = self.gate_fixture(root)
            state_file = root / ".harness/state.json"
            before = state_file.read_bytes()
            fingerprint = plan_hash(root)
            self.assertEqual(len(fingerprint), 64)
            with patch("workflow.stdin_is_interactive", return_value=True), \
                    patch("workflow.sys.stdin", FakeTTY("0000000Z\n")):
                with self.assertRaisesRegex(InteractiveApprovalError, "TTY_CONFIRMATION_MISMATCH"):
                    workflow.gate("PASS")
            self.assertEqual(before, state_file.read_bytes())
            output = io.StringIO()
            with patch("workflow.stdin_is_interactive", return_value=True), \
                    patch("workflow.sys.stdin", FakeTTY(fingerprint[:8] + "\n")):
                with contextlib.redirect_stdout(output):
                    workflow.gate("PASS")
            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["approved_plan"]["sha256"], fingerprint)
            self.assertEqual(state["active_ticket_id"], "T-001")
            self.assertIn(fingerprint, output.getvalue())

    def test_final_review_refuses_non_tty_and_wrong_prefix_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workflow, review, handoff = self.review_fixture(root)
            state_file = root / ".harness/state.json"
            before = state_file.read_bytes()
            artifact_dir = root / ".harness/verifications"
            before_artifacts = sorted(p.name for p in artifact_dir.glob("*.json"))
            for input_stream, code in ((io.StringIO(""), "TTY_CONFIRMATION_REQUIRED"),
                                       (FakeTTY("deadbeef\n"), "TTY_CONFIRMATION_MISMATCH")):
                with self.subTest(code=code):
                    with patch("workflow.stdin_is_interactive", return_value=input_stream.isatty()), \
                            patch("workflow.sys.stdin", input_stream):
                        with self.assertRaisesRegex(InteractiveApprovalError, code):
                            workflow.review("T-001", "PASS", review, handoff)
                    self.assertEqual(before, state_file.read_bytes())
                    self.assertEqual(before_artifacts,
                        sorted(p.name for p in artifact_dir.glob("*.json")))
            self.assertFalse((root / ".harness/reviews").exists())

    def test_final_review_correct_tty_prefix_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workflow, review, handoff = self.review_fixture(root)
            fingerprint = plan_hash(root)
            output = io.StringIO()
            with patch("workflow.stdin_is_interactive", return_value=True), \
                    patch("workflow.sys.stdin", FakeTTY(fingerprint[:8] + "\n")):
                with contextlib.redirect_stdout(output):
                    workflow.review("T-001", "PASS", review, handoff)
            state = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["project_status"], "COMPLETE")
            self.assertIsNotNone(state.get("final_verification"))
            self.assertIn(fingerprint, output.getvalue())

    def test_non_tty_cli_gate_returns_fixed_exit_code_and_state_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.gate_fixture(root)
            before = (root / ".harness/state.json").read_bytes()
            cmd = [sys.executable, str(root / "harness/runner/runner.py"),
                "gate-verdict", "--verdict", "PASS", "--project-root", str(root)]
            proc = subprocess.run(cmd, cwd=root, input="12345678\n", capture_output=True,
                text=True, encoding="utf-8", timeout=40)
            self.assertEqual(proc.returncode, APPROVAL_EXIT_CODE, proc.stderr)
            self.assertIn("TTY_CONFIRMATION_REQUIRED", proc.stderr)
            self.assertEqual(before, (root / ".harness/state.json").read_bytes())

    def test_non_tty_cli_final_review_returns_same_code_without_state_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, review, handoff = self.review_fixture(root)
            before = (root / ".harness/state.json").read_bytes()
            cmd = [sys.executable, str(root / "harness/runner/runner.py"),
                "review-verdict", "--ticket", "T-001", "--verdict", "PASS",
                "--review", str(review), "--handoff", str(handoff),
                "--trust-commands", "--project-root", str(root)]
            proc = subprocess.run(cmd, cwd=root, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(proc.returncode, APPROVAL_EXIT_CODE, proc.stderr)
            self.assertIn("TTY_CONFIRMATION_REQUIRED", proc.stderr)
            self.assertEqual(before, (root / ".harness/state.json").read_bytes())

    def test_final_non_tty_cannot_change_state_even_when_plan_is_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workflow, review, handoff = self.review_fixture(root)
            state_file = root / ".harness/state.json"
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["approved_plan"] = {"sha256": plan_hash(root)}
            state_file.write_text(json.dumps(state), encoding="utf-8")
            (root / "SPEC.md").write_text(
                "# Changed spec\\n\\n## User Stories\\n1. US-001: changed requirements\\n",
                encoding="utf-8")
            before = state_file.read_bytes()
            with patch("workflow.sys.stdin", io.StringIO("")):
                with self.assertRaisesRegex(InteractiveApprovalError, "TTY_CONFIRMATION_REQUIRED"):
                    workflow.review("T-001", "PASS", review, handoff)
            self.assertEqual(state_file.read_bytes(), before)

    @unittest.skipIf(sys.platform == "win32", "Unix pseudo-terminal only")
    def test_actual_pty_gate_accepts_typed_prefix(self):
        import os
        import pty
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.gate_fixture(root)
            prefix = plan_hash(root)[:8]
            master, slave = pty.openpty()
            try:
                cmd = [sys.executable, str(root / "harness/runner/runner.py"),
                    "gate-verdict", "--verdict", "PASS", "--project-root", str(root)]
                proc = subprocess.Popen(cmd, cwd=root, stdin=slave,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                os.close(slave)
                slave = -1
                os.write(master, (prefix + "\n").encode("ascii"))
                stdout, stderr = proc.communicate(timeout=60)
                self.assertEqual(proc.returncode, 0, stderr)
                self.assertIn(plan_hash(root), stdout)
                self.assertEqual(json.loads((root / ".harness/state.json").read_text(
                    encoding="utf-8"))["active_ticket_id"], "T-001")
            finally:
                if slave >= 0:
                    os.close(slave)
                os.close(master)

    def test_gate_plan_changed_during_prompt_never_commits_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workflow = self.gate_fixture(root)
            state_file = root / ".harness/state.json"
            before = state_file.read_bytes()

            def mutate_plan(_stage, _fingerprint):
                (root / "SPEC.md").write_text("changed during confirmation", encoding="utf-8")
                return True

            workflow.confirm_pass = mutate_plan
            with self.assertRaisesRegex(InteractiveApprovalError, "TTY_CONFIRMATION_STALE"):
                workflow.gate("PASS")
            self.assertEqual(before, state_file.read_bytes())

    def test_python_fixture_injection_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workflow = self.gate_fixture(root)
            calls = []
            workflow.confirm_pass = lambda stage, fingerprint: calls.append(
                (stage, fingerprint)) or True
            workflow.gate("PASS")
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], "TICKETS GATE")


if __name__ == "__main__":
    unittest.main()
