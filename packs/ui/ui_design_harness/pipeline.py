"""Create-only, versioned UI contract validation and story handoff pipeline.

This is a contract orchestration command, not the kernel's implementation/review
pipeline. It never approves an operator gate or claims browser UI acceptance.
"""
import json
from pathlib import Path
import re

from .contract import inspect_contract, load_json, render_documents, validate_contract
from .guidance import build_guidance


def _write_new(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(content)


def run_pipeline(contract_path, output_root):
    data = load_json(Path(contract_path).read_text(encoding="utf-8-sig"))
    version = data["metadata"]["version"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", version) or version in (".", ".."):
        raise ValueError("Unsafe version directory name")
    output_root = Path(output_root)
    target = output_root / version
    target.mkdir(parents=True, exist_ok=False)
    summary = dict(schema_version="0.1", status="FAIL", version=version,
        ui_acceptance="UNVERIFIED", discovery=None, design=None,
        final_gate_eligible=False, guidance=[], warnings=[],
        limitations=["No browser, visual or usability acceptance; does not approve a kernel gate"])
    try:
        for stage in ("discovery", "design"):
            docs = target / stage
            docs.mkdir()
            for name, content in render_documents(data, stage).items():
                _write_new(docs / name, content)
            receipt_path = target / (stage + "-receipt.json")
            receipt = inspect_contract(contract_path, stage, docs)
            _write_new(receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            summary[stage] = dict(status=receipt["status"], findings=receipt["findings"],
                receipt=str(receipt_path))
            summary["warnings"].extend(receipt.get("warnings", []))
            if receipt["status"] != "PASS":
                return summary
        for story in data["spec"]["stories"]:
            story_id = story["id"]
            report = build_guidance(contract_path, target / "design",
                target / "design-receipt.json", story_id)
            summary["guidance"].append(dict(story_id=story_id, status=report["status"],
                findings=report["findings"]))
            if report["status"] != "PASS":
                continue
            path = target / "guidance" / (story_id + ".json")
            _write_new(path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            summary["guidance"][-1]["output"] = str(path)
        summary["final_gate_eligible"] = not validate_contract(data, "final")
        summary["status"] = "PASS" if all(x["status"] == "PASS" for x in summary["guidance"]) else "FAIL"
        return summary
    finally:
        _write_new(target / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
