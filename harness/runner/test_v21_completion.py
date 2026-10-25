"""V2.1 completion regressions; intentionally negative checks for every new gate."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import test_support
PACK = test_support.SOURCE / "packs" / "ui"
sys.path.insert(0, str(PACK))
from ui_design_harness.contract import validate_contract, contract_warnings
from ui_design_harness.guidance import select_guidance
from ui_design_harness.pipeline import run_pipeline


def sample(which="e2e-case"):
    return json.loads((PACK / "examples" / which / "contract.json").read_text(encoding="utf-8"))


class ContractCompletionTests(unittest.TestCase):
    def test_basis_is_required_and_proposal_rejected_only_at_final(self):
        data = sample()
        data["brief"]["success_criteria"][0].pop("basis")
        self.assertIn("SUCCESS_BASIS_MISSING", [x["code"] for x in validate_contract(data, "design")])
        data["brief"]["success_criteria"][0]["basis"] = "proposal"
        self.assertEqual(validate_contract(data, "design"), [])
        self.assertIn("PROPOSAL_NOT_ACCEPTED", [x["code"] for x in validate_contract(data, "final")])

    def test_nonblocking_unknown_must_declare_destination(self):
        data = sample()
        data["brief"]["unknowns"][0].pop("deferred_to")
        self.assertIn("DEFER_DESTINATION_REQUIRED", [x["code"] for x in validate_contract(data, "discovery")])

    def test_implementation_deferred_unknown_blocks_guidance(self):
        data = sample()
        q = data["brief"]["unknowns"][0]
        q.update(resolution="", deferred_to="implementation")
        selection, findings = select_guidance(data, "US-001")
        self.assertIsNone(selection)
        self.assertTrue(any(f["code"] == "DEFERRED_UNKNOWN_DUE" and "Q-001" in f["path"]
            for f in findings), findings)

    def test_token_rule_id_substitutes_current_value(self):
        data = sample()
        rule = data["design"]["layout_rules"][0]
        rule["statement"] = "Container width at most @TOK-011"
        rule["token_ids"] = ["TOK-011"]
        self.assertEqual(validate_contract(data, "design"), [])
        selection, findings = select_guidance(data, "US-002")
        self.assertFalse(findings, findings)
        selected = next(x for x in selection["rules"] if x["id"] == rule["id"])
        self.assertIn("560px", selected["resolved_statement"])
        next(t for t in data["design"]["tokens"] if t["id"] == "TOK-011")["value"] = "640px"
        selection, findings = select_guidance(data, "US-002")
        self.assertFalse(findings, findings)
        self.assertIn("640px", next(x for x in selection["rules"] if x["id"] == rule["id"])["resolved_statement"])

    def test_undeclared_token_reference_is_rejected(self):
        data = sample()
        data["design"]["layout_rules"][0]["statement"] += " @TOK-011"
        self.assertIn("RULE_TOKEN_BINDING", [x["code"] for x in validate_contract(data, "design")])

    def test_shared_component_scoped_read_only(self):
        data = sample()
        shared = copy.deepcopy(data["design"]["components"][0])
        shared.update(id="CMP-099", name="Shared step indicator", parent_id=None,
            screen_ids=["SCR-002", "SCR-003"], shared=True)
        data["design"]["components"].append(shared)
        self.assertEqual(validate_contract(data, "design"), [])
        for story, screen, excluded in (("US-002", "SCR-002", "SCR-003"),
            ("US-003", "SCR-003", "SCR-002")):
            with self.subTest(story=story):
                selected, findings = select_guidance(data, story)
                self.assertFalse(findings, findings)
                ref = next(x for x in selected["shared_components"] if x["id"] == "CMP-099")
                self.assertTrue(ref["read_only"])
                self.assertEqual(ref["screen_ids"], [screen])
                self.assertNotIn(excluded, json.dumps(ref))

    def test_missing_variant_coverage_blocks_design(self):
        data = sample()
        screen = next(s for s in data["spec"]["screens"] if any(x["kind"] == "loading" for x in s["states"]))
        state = next(x for x in screen["states"] if x["kind"] == "loading")
        state["variant"] = "save"
        new_state = dict(state, variant="submit")
        screen["states"].append(new_state)
        for ac in data["spec"]["acceptance_criteria"]:
            if ac["screen_id"] == screen["id"] and ac["state"] == "loading":
                ac["variant"] = "save"
        errors = validate_contract(data, "design")
        self.assertTrue(any(x["code"] == "AC_COVERAGE" and "loading:submit" in x["path"]
            for x in errors), errors)

    def test_form_count_cannot_be_smaller_than_required(self):
        data = sample()
        data["brief"]["data_density"]["form"] = dict(field_count=12,
            required_count=13, conditional_groups=["payment"])
        self.assertIn("FORM_DENSITY", [x["code"] for x in validate_contract(data, "discovery")])

    def test_vague_ac_is_warning_not_failure(self):
        data = sample()
        ac = data["spec"]["acceptance_criteria"][0]
        ac["given"] = "開始畫面處於 default 條件"
        ac["when"] = "使用者進入此狀態並操作"
        self.assertEqual(validate_contract(data, "design"), [])
        self.assertTrue(any(x["severity"] == "warning" and x["code"] == "VAGUE_AC"
            for x in contract_warnings(data)))
        self.assertEqual(contract_warnings(sample("service-panel")), [])
        self.assertEqual(contract_warnings(sample("e2e-case")), [])

    def test_create_only_full_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "contract.json"
            source.write_text(json.dumps(sample("service-panel"), ensure_ascii=False), encoding="utf-8")
            result = run_pipeline(source, root / "outputs")
            self.assertEqual(result["status"], "PASS", result)
            self.assertEqual(result["discovery"]["status"], "PASS")
            self.assertEqual(result["design"]["status"], "PASS")
            self.assertEqual(len(result["guidance"]), 1)
            folder = root / "outputs" / sample("service-panel")["metadata"]["version"]
            self.assertTrue((folder / "discovery-receipt.json").is_file())
            self.assertTrue((folder / "design-receipt.json").is_file())
            self.assertTrue((folder / "guidance" / "US-001.json").is_file())
            self.assertTrue((folder / "summary.json").is_file())
            with self.assertRaises(FileExistsError):
                run_pipeline(source, root / "outputs")

    def test_readme_link_checker_flags_nonexistent_target(self):
        sys.path.insert(0, str(test_support.SOURCE / "scripts"))
        from check_readme_links import broken_links
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text("[missing](docs/not-here.md)", encoding="utf-8")
            errors = broken_links(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("docs/not-here.md", errors[0])


if __name__ == "__main__":
    unittest.main()
