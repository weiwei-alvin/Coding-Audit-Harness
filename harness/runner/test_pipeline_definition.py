"""T-006 pipeline definition tests: data-driven stages, resolution, init refusal.

The bundled default must reproduce the pre-T-006 hardcoded engine behavior; that
frozen table is the safety net for the cutover, not a second hardcoded source of
truth. Custom definitions prove add/remove/reorder/gate-types/hooks are data and
that the engine actually follows them at runtime. Every project lives in a temp dir.
"""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from pipeline_definition import (
    BUNDLED_DEFAULT_PATH,
    PipelineDefinitionError,
    load_definition,
    resolve_definition,
)
from state_transition import GateVerdict, StateTransitionEngine
from runner import HarnessRunner
from workflow import Workflow
from status import HarnessStatus

import test_support


def ticket_project(root, definition=None):
    """Temp project with tickets but no state, ready for init."""
    shutil.copytree(test_support.SOURCE / "harness", root / "harness",
        ignore=shutil.ignore_patterns("__pycache__"))
    (root / ".harness/tickets").mkdir(parents=True)
    (root / "SPEC.md").write_text(
        "# Spec\n\n## User Stories\n\n1. US-001: As a user, I want to add numbers, so that I get their sum\n",
        encoding="utf-8")
    (root / ".harness/tickets/T-001.md").write_text(
        "---\nid: T-001\ndepends_on: []\n---\n# Test ticket\n", encoding="utf-8")
    if definition is not None:
        (root / ".harness").mkdir(parents=True, exist_ok=True)
        (root / ".harness/pipeline.json").write_text(
            json.dumps(definition, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def custom_definition(stages, name="custom-pipeline"):
    return dict(schema_version="0.1", pipeline=name, stages=stages)


PLANNING = dict(kind="planning", gate_verdicts=["PASS", "FIX_REQUIRED", "USER_DECISION_REQUIRED"])

# Frozen pre-T-006 behavior. The bundled definition and every engine view must
# match these literals; the engine itself no longer stores them.
EXPECTED_ORDER = ["DISCOVERY", "SPEC", "TICKETS", "IMPLEMENTATION", "REVIEW"]
EXPECTED_TRANSITIONS = {
    ("DISCOVERY", "IN_PROGRESS"): ["READY_FOR_GATE"],
    ("DISCOVERY", "READY_FOR_GATE"): ["SPEC"],
    ("SPEC", "IN_PROGRESS"): ["READY_FOR_GATE"],
    ("SPEC", "READY_FOR_GATE"): ["TICKETS"],
    ("TICKETS", "IN_PROGRESS"): ["READY_FOR_GATE"],
    ("TICKETS", "READY_FOR_GATE"): ["IMPLEMENTATION"],
}
EXPECTED_GATE_VERDICTS = {
    "DISCOVERY": ["PASS", "FIX_REQUIRED", "USER_DECISION_REQUIRED"],
    "SPEC": ["PASS", "FIX_REQUIRED", "USER_DECISION_REQUIRED"],
    "TICKETS": ["PASS", "FIX_REQUIRED", "USER_DECISION_REQUIRED"],
}


class BundledDefaultEquivalenceTests(unittest.TestCase):
    """The bundled default file reproduces the frozen pre-T-006 behavior."""

    @classmethod
    def setUpClass(cls):
        cls.definition = load_definition(BUNDLED_DEFAULT_PATH)

    def test_planning_transitions_match_frozen_table(self):
        self.assertEqual(self.definition.planning_transitions(), EXPECTED_TRANSITIONS)

    def test_gate_verdicts_match_frozen_table(self):
        for stage_id, verdicts in EXPECTED_GATE_VERDICTS.items():
            self.assertEqual(self.definition.gate_verdicts(stage_id), verdicts)

    def test_stage_order_matches_frozen_order(self):
        self.assertEqual(self.definition.ids, EXPECTED_ORDER)

    def test_engine_compatibility_views_are_derived_from_definition(self):
        engine = StateTransitionEngine(Path("."))
        self.assertEqual(engine.STAGE_ORDER, EXPECTED_ORDER)
        self.assertEqual(engine.PLANNING_STAGE_TRANSITIONS, EXPECTED_TRANSITIONS)
        self.assertEqual({stage: [v.value for v in values] for stage, values in engine.GATE_VERDICTS.items()},
            EXPECTED_GATE_VERDICTS)
        self.assertEqual(engine.definition.ids, EXPECTED_ORDER)

    def test_entry_and_terminal_stages_are_declared(self):
        self.assertEqual([s["id"] for s in self.definition.stages if s.get("entry")], ["TICKETS"])
        self.assertEqual(self.definition.terminal_stage, "REVIEW")
        self.assertEqual(self.definition.first_stage, "DISCOVERY")
        self.assertEqual(self.definition.work_stage, "IMPLEMENTATION")
        self.assertEqual(self.definition.approval_stage, "TICKETS")

    def test_hooks_match_historical_special_cases(self):
        self.assertEqual(self.definition.hook("TICKETS", "on_gate_pass"), "validate_ticket_dependencies")
        self.assertEqual(self.definition.hook("IMPLEMENTATION", "on_enter"), "start_first_ticket")
        self.assertEqual(self.definition.next_stage("TICKETS"), "IMPLEMENTATION")
        self.assertEqual(self.definition.required_evidence_tiers("IMPLEMENTATION"), [])


class DataDrivenDefinitionTests(unittest.TestCase):
    """Stage add/remove/reorder and gate types come from the definition file."""

    def test_sequence_display_marks_conditional_stages(self):
        definition = custom_definition([
            dict(id="DISCOVERY", next="SPEC", **PLANNING),
            dict(id="SPEC", next="DESIGN", **PLANNING),
            dict(id="DESIGN", next="TICKETS", conditional=True, condition="spec_has_ui_stories", **PLANNING),
            dict(id="TICKETS", next="IMPLEMENTATION", **PLANNING),
            dict(id="IMPLEMENTATION", next="REVIEW", kind="execution"),
            dict(id="REVIEW", next=None, kind="execution", terminal=True),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline.json"
            path.write_text(json.dumps(definition), encoding="utf-8")
            loaded = load_definition(path)
        self.assertEqual(loaded.sequence_display(),
            "DISCOVERY -> SPEC -> DESIGN* -> TICKETS -> IMPLEMENTATION -> REVIEW")
        self.assertTrue(loaded.is_conditional("DESIGN"))
        self.assertFalse(loaded.is_conditional("SPEC"))

    def test_added_and_reordered_stages_change_the_tables(self):
        definition = custom_definition([
            dict(id="DISCOVERY", next="SPEC", **PLANNING),
            dict(id="SPEC", next="TICKETS", **PLANNING),
            dict(id="TICKETS", next="IMPLEMENTATION", **PLANNING),
            dict(id="IMPLEMENTATION", next="VERIFY", kind="execution"),
            dict(id="VERIFY", next="REVIEW", kind="execution"),
            dict(id="REVIEW", next=None, kind="execution", terminal=True),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline.json"
            path.write_text(json.dumps(definition), encoding="utf-8")
            loaded = load_definition(path)
        self.assertEqual(loaded.ids, ["DISCOVERY", "SPEC", "TICKETS", "IMPLEMENTATION", "VERIFY", "REVIEW"])
        self.assertEqual(loaded.planning_transitions()[("SPEC", "READY_FOR_GATE")], ["TICKETS"])
        self.assertEqual(loaded.next_stage("IMPLEMENTATION"), "VERIFY")
        self.assertEqual(loaded.terminal_stage, "REVIEW")

    def test_removed_stages_shrink_the_tables(self):
        definition = custom_definition([
            dict(id="DISCOVERY", next="IMPLEMENTATION", **PLANNING),
            dict(id="IMPLEMENTATION", next=None, kind="execution", terminal=True),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline.json"
            path.write_text(json.dumps(definition), encoding="utf-8")
            loaded = load_definition(path)
        self.assertEqual(loaded.ids, ["DISCOVERY", "IMPLEMENTATION"])
        self.assertEqual(loaded.planning_transitions(),
            {("DISCOVERY", "IN_PROGRESS"): ["READY_FOR_GATE"], ("DISCOVERY", "READY_FOR_GATE"): ["IMPLEMENTATION"]})

    def test_gate_verdicts_are_per_stage_data(self):
        definition = custom_definition([
            dict(id="DISCOVERY", next="SPEC", gate_verdicts=["PASS"], **{k: v for k, v in PLANNING.items() if k != "gate_verdicts"}),
            dict(id="SPEC", next="IMPLEMENTATION", gate_verdicts=["PASS", "USER_DECISION_REQUIRED"], **{k: v for k, v in PLANNING.items() if k != "gate_verdicts"}),
            dict(id="IMPLEMENTATION", next=None, kind="execution", terminal=True),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline.json"
            path.write_text(json.dumps(definition), encoding="utf-8")
            loaded = load_definition(path)
        self.assertEqual(loaded.gate_verdicts("DISCOVERY"), ["PASS"])
        self.assertEqual(loaded.gate_verdicts("SPEC"), ["PASS", "USER_DECISION_REQUIRED"])
        with self.assertRaises(PipelineDefinitionError):
            loaded.gate_verdicts("IMPLEMENTATION")

    def test_required_evidence_tiers_are_stage_data(self):
        definition = custom_definition([
            dict(id="DISCOVERY", next="IMPLEMENTATION", **PLANNING),
            dict(id="IMPLEMENTATION", next=None, kind="execution", terminal=True,
                required_evidence_tiers=["deterministic", "captured", "declared"]),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline.json"
            path.write_text(json.dumps(definition), encoding="utf-8")
            loaded = load_definition(path)
        self.assertEqual(loaded.required_evidence_tiers("IMPLEMENTATION"),
            ["deterministic", "captured", "declared"])
        self.assertEqual(loaded.required_evidence_tiers("DISCOVERY"), [])

    def test_invalid_definitions_are_refused_with_reasons(self):
        cases = {
            "unknown next": custom_definition([dict(id="DISCOVERY", next="NOWHERE", **PLANNING)]),
            "two terminals": custom_definition([
                dict(id="DISCOVERY", next="SPEC", **PLANNING),
                dict(id="SPEC", next=None, kind="execution", terminal=True),
                dict(id="EXTRA", next=None, kind="execution", terminal=True)]),
            "terminal not last": custom_definition([
                dict(id="DISCOVERY", next=None, kind="execution", terminal=True),
                dict(id="SPEC", next="IMPLEMENTATION", **PLANNING)]),
            "missing gate verdicts": custom_definition([
                dict(id="DISCOVERY", next="IMPLEMENTATION", kind="planning"),
                dict(id="IMPLEMENTATION", next=None, kind="execution", terminal=True)]),
            "tiers on planning stage": custom_definition([
                dict(id="DISCOVERY", next="IMPLEMENTATION", required_evidence_tiers=["deterministic"], **PLANNING),
                dict(id="IMPLEMENTATION", next=None, kind="execution", terminal=True)]),
        }
        for label, definition in cases.items():
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "pipeline.json"
                path.write_text(json.dumps(definition), encoding="utf-8")
                with self.assertRaises(PipelineDefinitionError, msg=label) as caught:
                    load_definition(path)
            self.assertTrue(str(caught.exception), label)

    def test_missing_and_corrupt_files_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PipelineDefinitionError):
                load_definition(Path(tmp) / "absent.json")
            broken = Path(tmp) / "broken.json"
            broken.write_text("{ not json", encoding="utf-8")
            with self.assertRaises(PipelineDefinitionError):
                load_definition(broken)


class ResolutionAndInitTests(unittest.TestCase):
    """Resolution order, init refusal, and the recorded definition."""

    def test_resolution_prefers_explicit_then_project_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = ticket_project(Path(tmp))
            project_definition = custom_definition([
                dict(id="DISCOVERY", next="IMPLEMENTATION", **PLANNING),
                dict(id="IMPLEMENTATION", next=None, kind="execution", terminal=True)],
                name="project-owned")
            (root / ".harness/pipeline.json").write_text(
                json.dumps(project_definition), encoding="utf-8")
            explicit = root / "explicit.json"
            explicit.write_text(json.dumps(custom_definition([
                dict(id="DISCOVERY", next="IMPLEMENTATION", **PLANNING),
                dict(id="IMPLEMENTATION", next=None, kind="execution", terminal=True)],
                name="explicit-pick")), encoding="utf-8")
            self.assertEqual(resolve_definition(root).name, "project-owned")
            self.assertEqual(resolve_definition(root, explicit).name, "explicit-pick")

    def test_init_refuses_without_a_project_definition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = ticket_project(Path(tmp))
            with self.assertRaises(ValueError) as caught:
                Workflow(HarnessRunner(root)).initialize()
        message = str(caught.exception)
        self.assertIn("pipeline definition", message)
        self.assertIn("pipeline.default.json", message)

    def test_init_adopts_the_project_definition_and_records_it(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = ticket_project(Path(tmp))
            shutil.copyfile(BUNDLED_DEFAULT_PATH, root / ".harness/pipeline.json")
            Workflow(HarnessRunner(root)).initialize()
            state = json.loads((root / ".harness/state.json").read_text(encoding="utf-8"))
            recorded = state["pipeline_definition"]
            self.assertEqual(state["pipeline_stage"], "TICKETS")
            self.assertEqual(state["tickets"]["T-001"]["status"], "TODO")
            self.assertEqual(recorded["pipeline"], "code-default")
            self.assertEqual(recorded["sha256"],
                hashlib.sha256((root / ".harness/pipeline.json").read_bytes()).hexdigest())

    def test_init_refuses_when_no_entry_stage_is_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = ticket_project(Path(tmp), custom_definition([
                dict(id="DISCOVERY", next="IMPLEMENTATION", **PLANNING),
                dict(id="IMPLEMENTATION", next=None, kind="execution", terminal=True)]))
            with self.assertRaises(ValueError) as caught:
                Workflow(HarnessRunner(root)).initialize()
        self.assertIn("entry stage", str(caught.exception))


class EngineCutoverTests(unittest.TestCase):
    """The runtime engine follows the resolved definition, not historical tables."""

    def runtime_project(self, root, definition, stage, status="READY_FOR_GATE"):
        ticket_project(root, definition)
        state = dict(schema_version="1.1", project_status="IN_PROGRESS", pipeline_stage=stage,
            stage_status=status, active_ticket_id=None, pause=None,
            tickets={"T-001": dict(status="TODO", review_attempts=0, active_findings=[])},
            findings={})
        (root / ".harness/state.json").write_text(json.dumps(state), encoding="utf-8")
        return state

    def test_engine_follows_custom_stage_order_and_gate_types(self):
        definition = custom_definition([
            dict(id="CONCEPT", next="BUILD", gate_verdicts=["PASS"], kind="planning"),
            dict(id="BUILD", next="SHIP", kind="execution", on_enter="start_first_ticket"),
            dict(id="SHIP", next=None, kind="execution", terminal=True),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.runtime_project(root, definition, "CONCEPT")
            engine = StateTransitionEngine(root)
            self.assertFalse(engine.advance_planning_stage(state, GateVerdict.FIX_REQUIRED).success)
            self.assertFalse(engine.set_stage_ready_for_gate(state).success)
            self.assertFalse(engine.start_ticket(dict(state, stage_status="IN_PROGRESS"), "T-001").success)
            result = engine.advance_planning_stage(state, GateVerdict.PASS)
            self.assertTrue(result.success, result.error)
            self.assertEqual(result.new_state["pipeline_stage"], "BUILD")
            self.assertEqual(result.new_state["active_ticket_id"], "T-001")
            runner = HarnessRunner(root)
            valid, error = runner.validate_state(result.new_state)
            self.assertTrue(valid, error)
            build_state = dict(result.new_state,
                tickets={"T-002": dict(status="TODO", review_attempts=0, active_findings=[])},
                active_ticket_id=None)
            (root / ".harness/state.json").write_text(json.dumps(build_state), encoding="utf-8")
            self.assertTrue(runner.can_start_ticket("T-002")[0])
            started = engine.start_ticket(build_state, "T-002")
            self.assertTrue(started.success, started.error)

    def test_on_enter_hook_is_data(self):
        for hook, expected in ((None, None), ("start_first_ticket", "T-001")):
            stages = [
                dict(id="CONCEPT", next="BUILD", gate_verdicts=["PASS"], kind="planning"),
                dict(id="BUILD", next=None, kind="execution", terminal=True),
            ]
            if hook:
                stages[1]["on_enter"] = hook
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                state = self.runtime_project(root, custom_definition(stages), "CONCEPT")
                result = StateTransitionEngine(root).advance_planning_stage(state, GateVerdict.PASS)
                self.assertTrue(result.success, result.error)
                self.assertEqual(result.new_state["pipeline_stage"], "BUILD")
                self.assertEqual(result.new_state["active_ticket_id"], expected)

    def test_recorded_definition_source_wins(self):
        project = custom_definition([
            dict(id="DISCOVERY", next="IMPLEMENTATION", **PLANNING),
            dict(id="IMPLEMENTATION", next=None, kind="execution", terminal=True),
        ], name="project-owned")
        recorded = custom_definition([
            dict(id="START", next="SHIP", gate_verdicts=["PASS"], kind="planning"),
            dict(id="SHIP", next=None, kind="execution", terminal=True),
        ], name="recorded-owner")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.runtime_project(root, project, "START")
            recorded_path = root / "recorded.json"
            recorded_path.write_text(json.dumps(recorded), encoding="utf-8")
            state["pipeline_definition"] = dict(source=str(recorded_path), pipeline="recorded-owner")
            result = StateTransitionEngine(root).advance_planning_stage(state, GateVerdict.PASS)
            self.assertTrue(result.success, result.error)
            self.assertEqual(result.new_state["pipeline_stage"], "SHIP")

    def test_missing_recorded_definition_is_reported_not_guessed(self):
        project = custom_definition([
            dict(id="DISCOVERY", next="IMPLEMENTATION", **PLANNING),
            dict(id="IMPLEMENTATION", next=None, kind="execution", terminal=True),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.runtime_project(root, project, "DISCOVERY")
            state["pipeline_definition"] = dict(source=str(root / "gone.json"))
            result = StateTransitionEngine(root).advance_planning_stage(state, GateVerdict.PASS)
            self.assertFalse(result.success)
            self.assertIn("Recorded pipeline definition", result.error)

    def test_legacy_state_without_record_uses_bundled_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.runtime_project(root, None, "DISCOVERY")
            result = StateTransitionEngine(root).advance_planning_stage(state, GateVerdict.PASS)
            self.assertTrue(result.success, result.error)
            self.assertEqual(result.new_state["pipeline_stage"], "SPEC")

    def test_custom_stage_is_accepted_by_state_schema(self):
        definition = custom_definition([
            dict(id="CONCEPT", next="BUILD", gate_verdicts=["PASS"], kind="planning"),
            dict(id="BUILD", next=None, kind="execution", terminal=True),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = self.runtime_project(root, definition, "CONCEPT")
            valid, error = HarnessRunner(root).validate_state(state)
            self.assertTrue(valid, error)
            state.update(pipeline_stage="BUILD", stage_status="IN_PROGRESS", active_ticket_id="T-001")
            valid, error = HarnessRunner(root).validate_state(state)
            self.assertTrue(valid, error)


class StatusWiringTests(unittest.TestCase):
    """Status reports the definition's stage sequence with conditional markers."""

    def test_status_reports_definition_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            test_support.fixture(root)
            (root / ".harness/pipeline.json").write_text(json.dumps(custom_definition([
                dict(id="DISCOVERY", next="SPEC", **PLANNING),
                dict(id="SPEC", next="DESIGN", **PLANNING),
                dict(id="DESIGN", next="TICKETS", conditional=True,
                    condition="spec_has_ui_stories", **PLANNING),
                dict(id="TICKETS", next="IMPLEMENTATION", **PLANNING),
                dict(id="IMPLEMENTATION", next="REVIEW", kind="execution"),
                dict(id="REVIEW", next=None, kind="execution", terminal=True)])),
                encoding="utf-8")
            status = HarnessStatus(root).get_status()
        self.assertEqual(status["pipeline_stages"],
            "DISCOVERY -> SPEC -> DESIGN* -> TICKETS -> IMPLEMENTATION -> REVIEW")
        self.assertTrue(status["pipeline_definition_source"].endswith("pipeline.json"))

    def test_status_prefers_recorded_definition_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            test_support.fixture(root)
            probe = custom_definition([
                dict(id="IDEA", next="BUILD", gate_verdicts=["PASS"], kind="planning"),
                dict(id="BUILD", next="DONE", kind="execution"),
                dict(id="DONE", next=None, kind="execution", terminal=True),
            ], name="recorded-probe")
            probe_path = root / "recorded-probe.json"
            probe_path.write_text(json.dumps(probe), encoding="utf-8")
            state_path = root / ".harness/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["pipeline_definition"] = dict(source=str(probe_path), pipeline="recorded-probe")
            state_path.write_text(json.dumps(state), encoding="utf-8")
            status = HarnessStatus(root).get_status()
        self.assertEqual(status["pipeline_stages"], "IDEA -> BUILD -> DONE")
        self.assertTrue(status["pipeline_definition_source"].endswith("recorded-probe.json"))


if __name__ == "__main__":
    unittest.main()
