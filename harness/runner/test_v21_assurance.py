"""V2.1 regression tests: incomplete contracts and stale gate evidence fail closed."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import test_support
import test_pack_gates

PACK = test_support.SOURCE / "packs" / "ui"
sys.path.insert(0, str(PACK))
from ui_design_harness.contract import (  # noqa: E402
    contrast_ratio, inspect_contract, render_documents, validate_contract
)
from state_transition import GateVerdict, StateTransitionEngine


def example():
    return json.loads((PACK / "examples/e2e-case/contract.json").read_text(encoding="utf-8"))


class ContractAssuranceTests(unittest.TestCase):
    def test_bundled_case_still_validates(self):
        self.assertEqual(validate_contract(example(), "design"), [])

    def test_placeholder_in_problem_or_ac_is_rejected(self):
        for phrase in ("待補充", "之後再定", "N/A", "TBD"):
            for key in ("problem", "then"):
                with self.subTest(phrase=phrase, key=key):
                    data = example()
                    if key == "problem":
                        data["brief"]["problem"] = "此處" + phrase
                    else:
                        data["spec"]["acceptance_criteria"][0]["then"] = "驗收內容：" + phrase
                    self.assertTrue(any(x["code"] == "UNRESOLVED_VALUE"
                        for x in validate_contract(data, "design")))

    def test_project_specific_placeholder_is_rejected(self):
        data = example()
        data["brief"]["placeholder_terms"] = ["待討論"]
        data["brief"]["problem"] = "內容待討論"
        self.assertTrue(any(x["code"] == "UNRESOLVED_VALUE"
            for x in validate_contract(data, "design")))

    def test_malformed_color_and_spacing_tokens_are_schema_errors(self):
        for category, bad in (("color", "N/A"), ("spacing", "12"), ("layout", "960")):
            with self.subTest(category=category):
                data = example()
                token = next(t for t in data["design"]["tokens"] if t["category"] == category)
                token["value"] = bad
                self.assertTrue(any(x["code"] == "SCHEMA"
                    for x in validate_contract(data, "design")))

    def test_component_boundary_contrast_computed(self):
        data = example()
        data["design"]["tokens"][0]["value"] = "#B9BFB6"
        data["design"]["tokens"][1]["value"] = "#FFFFFF"
        data["design"]["color_pairs"] = [dict(id="PAIR-001",
            foreground_token_id="TOK-001", background_token_id="TOK-002",
            usage="component_boundary")]
        self.assertAlmostEqual(contrast_ratio("#B9BFB6", "#FFFFFF"), 1.88, delta=0.02)
        findings = validate_contract(data, "design")
        self.assertTrue(any(x["code"] == "COLOR_CONTRAST" and "3.0:1" in x["message"]
            for x in findings), findings)

    def test_well_contrasted_pair_passes(self):
        data = example()
        data["design"]["color_pairs"] = [dict(id="PAIR-001",
            foreground_token_id="TOK-003", background_token_id="TOK-002",
            usage="text")]
        self.assertEqual(validate_contract(data, "design"), [])

    def test_cross_story_root_is_rejected_at_design_gate(self):
        data = example()
        root = next(c for c in data["design"]["components"] if c["id"] == "CMP-002")
        root["screen_ids"].append("SCR-003")
        findings = validate_contract(data, "design")
        self.assertTrue(any(f["code"] == "SCOPE_GAP" and "CMP-002" in f["message"]
            for f in findings), findings)


class GateEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.root = test_pack_gates.ui_project(
            "DESIGN", [dict(test_pack_gates.COLLECT_STEP)], {})
        definition_path = self.root / "pack-definition.json"
        definition = json.loads(definition_path.read_text(encoding="utf-8"))
        self.config = json.loads((PACK / "pipeline.json").read_text(encoding="utf-8"))["stages"][2]["gate_receipt"]
        definition["stages"][2]["gate_receipt"] = self.config
        definition_path.write_text(json.dumps(definition), encoding="utf-8")
        (self.root / "packs").mkdir()
        shutil.copytree(PACK, self.root / "packs/ui",
            ignore=shutil.ignore_patterns("__pycache__"))
        self.source = self.root / "contract.json"
        self.source.write_text(json.dumps(example(), ensure_ascii=False), encoding="utf-8")
        self.documents = self.root / "docs"
        self.documents.mkdir()
        for name, content in render_documents(example(), "design").items():
            (self.documents / name).write_bytes(content.encode("utf-8"))
        self.receipt = self.root / "design-receipt.json"
        self.receipt.write_text(json.dumps(inspect_contract(self.source, "design", self.documents)),
            encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def gate(self, stage="DESIGN", history=None):
        state = json.loads((self.root / ".harness/state.json").read_text(encoding="utf-8"))
        state["pipeline_stage"] = stage
        state["stage_status"] = "READY_FOR_GATE"
        if history is not None:
            state["stage_gates"] = history
        return StateTransitionEngine(self.root).process_gate_verdict(state, GateVerdict.PASS)

    def test_valid_receipt_allows_design_pass(self):
        report = self.gate()
        self.assertTrue(report.success, report.error)

    def test_missing_receipt_rejected(self):
        self.receipt.unlink()
        report = self.gate()
        self.assertFalse(report.success)
        self.assertIn("Gate evidence", report.error)

    def test_changed_contract_rejected(self):
        self.source.write_text(self.source.read_text(encoding="utf-8") + " ", encoding="utf-8")
        report = self.gate()
        self.assertFalse(report.success)
        self.assertIn("source_hash", report.error)

    def test_changed_engine_rejected(self):
        path = self.root / "packs/ui/ui_design_harness/contract.py"
        path.write_text(path.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
        report = self.gate()
        self.assertFalse(report.success)
        self.assertIn("engine_hash", report.error)

    def test_changed_document_rejected(self):
        path = self.documents / "DESIGN.md"
        path.write_text("stale", encoding="utf-8")
        report = self.gate()
        self.assertFalse(report.success)
        self.assertIn("document", report.error)

    def test_tickets_gate_rejects_stale_design_receipt(self):
        self.source.write_text(self.source.read_text(encoding="utf-8") + " ", encoding="utf-8")
        report = self.gate("TICKETS", {"DESIGN": "PASS"})
        self.assertFalse(report.success)
        self.assertIn("evidence is stale", report.error)


if __name__ == "__main__":
    unittest.main()
