"""T-009 ui-pack registration and the conditional-stage guard.

The pack is data plus the absorbed stateless CLI: a stage set registered via a
pipeline definition file (kernel code carries no UI words), typed commands
declared in golden_path.json with the T-007 types, and one new generic hook:
require_conditional_gates. That hook refuses a planning gate PASS until every
active conditional stage has a recorded PASS gate. Pure-code projects run the
unchanged code-default pipeline and never see the hook. Every project is
disposable.
"""
import json
from pathlib import Path
import tempfile
import unittest

from pipeline_definition import BUNDLED_DEFAULT_PATH, PipelineDefinitionError, load_definition
from state_transition import GateVerdict, StateTransitionEngine
import test_support

PACK_PIPELINE_PATH = test_support.SOURCE / "packs" / "ui" / "pipeline.json"

PLANNING = dict(kind="planning", gate_verdicts=["PASS", "FIX_REQUIRED", "USER_DECISION_REQUIRED"])


def ui_style_definition():
    return dict(schema_version="0.1", pipeline="ui-pack-test", stages=[
        dict(id="DISCOVERY", next="SPEC", **PLANNING),
        dict(id="SPEC", next="DESIGN", **PLANNING),
        dict(id="DESIGN", next="TICKETS", conditional=True,
            condition="golden_path_declares_collector", **PLANNING),
        dict(id="TICKETS", next="IMPLEMENTATION", on_gate_pass=[
            "validate_ticket_dependencies", "require_conditional_gates"], **PLANNING),
        dict(id="IMPLEMENTATION", next="REVIEW", kind="execution"),
        dict(id="REVIEW", next=None, kind="execution", terminal=True),
    ])


COLLECT_STEP = dict(id="GP-001", description="collect", user_story_ids=["US-001"],
    ticket_ids=["T-001"], verification_command=["python", "collect.py"],
    expected_output="", verification_type="collector")
ASSERTION_STEP = dict(id="GP-001", description="scan", user_story_ids=["US-001"],
    ticket_ids=["T-001"], verification_command=["python", "check.py"], expected_output="")


def ui_project(stage, steps, stage_gates):
    """Disposable project pinned to the ui-style definition file."""
    tmp = tempfile.TemporaryDirectory(prefix="harness-pack-")
    root = Path(tmp.name)
    try:
        state = test_support.fixture(root, count=1)  # copies the kernel copy and baseline project files
        state.update(pipeline_stage=stage, stage_status="READY_FOR_GATE", active_ticket_id=None)
        definition = root / "pack-definition.json"
        definition.write_text(json.dumps(ui_style_definition()), encoding="utf-8")
        state["pipeline_definition"] = dict(source=str(definition), sha256="", pipeline="ui-pack-test")
        if stage_gates is not None:
            state["stage_gates"] = stage_gates
        (root / ".harness/golden_path.json").write_text(
            json.dumps({"steps": steps}), encoding="utf-8")
        (root / ".harness/state.json").write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        tmp.cleanup()
        raise
    return tmp, root


class PackPipelineDefinitionTests(unittest.TestCase):
    """packs/ui/pipeline.json loads and the bundled default stays UI-free."""

    def test_bundled_pack_pipeline_loads_and_marks_conditional_design(self):
        loaded = load_definition(PACK_PIPELINE_PATH)
        self.assertEqual(loaded.name, "ui-pack")
        self.assertIn("DESIGN*", loaded.sequence_display())
        self.assertTrue(loaded.is_conditional("DESIGN"))
        self.assertEqual(loaded.gate_hooks("TICKETS"),
            ["validate_ticket_dependencies", "require_conditional_gates"])
        self.assertEqual(loaded.approval_stage, "TICKETS")
        self.assertEqual(loaded.required_evidence_tiers("REVIEW"),
            ["deterministic", "captured", "declared"])

    def test_bundled_default_stays_free_of_ui_stages_and_hooks(self):
        loaded = load_definition(BUNDLED_DEFAULT_PATH)
        self.assertNotIn("DESIGN", loaded.ids)
        self.assertEqual(loaded.gate_hooks("TICKETS"), ["validate_ticket_dependencies"])
        self.assertEqual(loaded.required_evidence_tiers("REVIEW"), [])

    def test_unknown_gate_hook_is_refused(self):
        definition = ui_style_definition()
        definition["stages"][3]["on_gate_pass"] = "unknown_hook"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline.json"
            path.write_text(json.dumps(definition), encoding="utf-8")
            with self.assertRaisesRegex(PipelineDefinitionError, "unknown_hook"):
                load_definition(path)

    def test_duplicate_gate_hooks_are_refused(self):
        definition = ui_style_definition()
        definition["stages"][3]["on_gate_pass"] = [
            "validate_ticket_dependencies", "validate_ticket_dependencies"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline.json"
            path.write_text(json.dumps(definition), encoding="utf-8")
            with self.assertRaisesRegex(PipelineDefinitionError, "uniqueItems|not valid under any"):
                load_definition(path)

    def test_unenforceable_conditions_are_refused_when_hook_is_declared(self):
        definition = ui_style_definition()
        definition["stages"][2]["condition"] = "spec_has_ui_stories"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline.json"
            path.write_text(json.dumps(definition), encoding="utf-8")
            with self.assertRaisesRegex(PipelineDefinitionError, "supported conditions"):
                load_definition(path)

    def test_string_hook_stays_accepted_alongside_arrays(self):
        definition = ui_style_definition()
        definition["stages"][3]["on_gate_pass"] = "validate_ticket_dependencies"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline.json"
            path.write_text(json.dumps(definition), encoding="utf-8")
            self.assertEqual(load_definition(path).gate_hooks("TICKETS"),
                ["validate_ticket_dependencies"])


class WalkRecordsGateHistoryTests(unittest.TestCase):
    """PASSing a planning gate records stage_gates, including a DESIGN leg."""

    def run_pass(self, stage, stage_gates):
        tmp, root = ui_project(stage, [dict(COLLECT_STEP)], stage_gates)
        try:
            state = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
            engine = StateTransitionEngine(root)
            result = engine.process_gate_verdict(state, GateVerdict.PASS)
        finally:
            tmp.cleanup()
        return result

    def test_design_pass_is_recorded_and_advances_to_tickets(self):
        result = self.run_pass("DESIGN", {})
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.new_state["stage_gates"].get("DESIGN"), "PASS")
        self.assertEqual(result.new_state["pipeline_stage"], "TICKETS")

    def test_tickets_pass_appends_to_the_existing_history(self):
        result = self.run_pass("TICKETS", dict(DESIGN="PASS"))
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.new_state["stage_gates"],
            dict(DESIGN="PASS", TICKETS="PASS"))
        self.assertEqual(result.new_state["pipeline_stage"], "IMPLEMENTATION")


class ConditionalGateGuardTests(unittest.TestCase):
    """require_conditional_gates refuses TICKETS PASS without a DESIGN PASS."""

    def run_gate(self, steps, stage_gates):
        tmp, root = ui_project("TICKETS", steps, stage_gates)
        try:
            state = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
            engine = StateTransitionEngine(root)
            return engine.process_gate_verdict(state, GateVerdict.PASS)
        finally:
            tmp.cleanup()

    def test_active_design_without_recorded_pass_refuses_and_names_reason(self):
        result = self.run_gate([dict(COLLECT_STEP)], {})
        self.assertFalse(result.success)
        self.assertIn("Conditional stage DESIGN", result.error)
        self.assertIn("golden_path_declares_collector", result.error)

    def test_legacy_state_without_history_refuses(self):
        result = self.run_gate([dict(COLLECT_STEP)], None)
        self.assertFalse(result.success)
        self.assertIn("DESIGN", result.error)

    def test_recorded_design_pass_lets_the_gate_through(self):
        result = self.run_gate([dict(COLLECT_STEP)], dict(DESIGN="PASS"))
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.new_state["pipeline_stage"], "IMPLEMENTATION")

    def test_inactive_condition_does_not_require_design(self):
        result = self.run_gate([dict(id=ASSERTION_STEP["id"], **{
            k: v for k, v in ASSERTION_STEP.items() if k != "id"})], {})
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.new_state["pipeline_stage"], "IMPLEMENTATION")


class CodeDefaultGuardFreeTests(unittest.TestCase):
    """Pure-code projects keep existing behavior with the default pipeline."""

    def run_gate(self, state_stage_gates):
        tmp = tempfile.TemporaryDirectory(prefix="harness-code-")
        try:
            root = Path(tmp.name)
            state = test_support.fixture(root, count=1)  # default pipeline, TICKETS gate-ready
            if state_stage_gates is not None:
                state["stage_gates"] = state_stage_gates
                (root / ".harness/state.json").write_text(json.dumps(state), encoding="utf-8")
            engine = StateTransitionEngine(root)
            result = engine.process_gate_verdict(state, GateVerdict.PASS)
        finally:
            tmp.cleanup()
        return result

    def test_default_pipeline_gate_passes_without_any_ui_stage(self):
        result = self.run_gate(None)
        self.assertTrue(result.success, result.error)
        self.assertEqual(result.new_state["pipeline_stage"], "IMPLEMENTATION")

    def test_recording_is_additive_and_does_not_block_legacy_states(self):
        result = self.run_gate(None)
        self.assertEqual(result.new_state["stage_gates"].get("TICKETS"), "PASS")


if __name__ == "__main__":
    unittest.main()
