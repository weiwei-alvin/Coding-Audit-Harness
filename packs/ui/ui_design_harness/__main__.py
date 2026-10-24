"""Portable CLI. check: 0 PASS, 1 contract FAIL, 2 invocation or I/O error.
guidance: 0 PASS, 1 reject, 2 invocation or I/O error.
rules: 0 no blocking/major violation, 1 violation or empty scan, 2 invocation or I/O error.
collect: 0 assertions passed, 1 console/name/walkthrough failure, 2 invocation or I/O error.
review: 0 verdict PASS, 1 FIX_REQUIRED/PAUSED/REJECTED, 2 invocation or I/O error.
fix: 0 APPROVED_SCOPE/DESIGN_CHANGE_DECLARED, 1 scope/finding/change rejection, 2 invocation or I/O error."""
import argparse
import json
from pathlib import Path
import sys
from .collector import collect_evidence
from .contract import inspect_contract, load_json, render_documents, validate_contract
from .guidance import build_guidance
from .review import run_fix, run_review
from .rules import exit_code, scan_target

def write_new(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(content)

def main(argv=None):
    parser = argparse.ArgumentParser(description="Discovery and Design contract gates; no UI acceptance claim.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "render"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--contract", type=Path, required=True)
        cmd.add_argument("--stage", choices=("discovery", "design"), required=True)
        if name == "check":
            cmd.add_argument("--documents", type=Path)
            cmd.add_argument("--receipt", type=Path)
        else:
            cmd.add_argument("--output", type=Path, required=True)
    guidance = sub.add_parser("guidance")
    guidance.add_argument("--contract", type=Path, required=True)
    guidance.add_argument("--documents", type=Path, required=True)
    guidance.add_argument("--receipt", type=Path, required=True)
    guidance.add_argument("--story", required=True)
    guidance.add_argument("--output", type=Path)
    rules_cmd = sub.add_parser("rules")
    rules_cmd.add_argument("--input", type=Path, required=True)
    rules_cmd.add_argument("--rules", type=Path)
    rules_cmd.add_argument("--output", type=Path)
    collect_cmd = sub.add_parser("collect")
    collect_cmd.add_argument("--input", type=Path, required=True)
    collect_cmd.add_argument("--output", type=Path, required=True)
    collect_cmd.add_argument("--tabs", type=int, default=12)
    collect_cmd.add_argument("--wait-ms", type=int, default=50)
    review_cmd = sub.add_parser("review")
    review_cmd.add_argument("--input", type=Path, required=True)
    review_cmd.add_argument("--record", type=Path, required=True)
    review_cmd.add_argument("--previous", type=Path)
    review_cmd.add_argument("--retry-limit", type=int, default=3)
    review_cmd.add_argument("--output", type=Path)
    fix_cmd = sub.add_parser("fix")
    fix_cmd.add_argument("--input", type=Path, required=True)
    fix_cmd.add_argument("--previous", type=Path, required=True)
    fix_cmd.add_argument("--fixes", type=Path, required=True)
    fix_cmd.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            result = inspect_contract(args.contract, args.stage, args.documents)
            code = 0 if result["status"] == "PASS" else 1
            text = json.dumps(result, ensure_ascii=False, indent=2)
            if args.receipt is not None:
                write_new(args.receipt, text + "\n")
        elif args.command == "guidance":
            result = build_guidance(args.contract, args.documents, args.receipt, args.story)
            code = 0 if result["status"] == "PASS" else 1
            text = json.dumps(result, ensure_ascii=False, indent=2)
            if args.output is not None and result["status"] == "PASS":
                write_new(args.output, text + "\n")
        elif args.command == "rules":
            result = scan_target(args.input, args.rules)
            code = exit_code(result["status"])
            text = json.dumps(result, ensure_ascii=False, indent=2)
            if args.output is not None:
                write_new(args.output, text + "\n")
        elif args.command == "collect":
            result = collect_evidence(args.input, args.output, args.tabs, args.wait_ms)
            code = 0 if result["status"] == "PASS" else 1
            text = json.dumps(result, ensure_ascii=False, indent=2)
        elif args.command == "review":
            result = run_review(args.input, args.record, args.previous, args.retry_limit)
            code = 0 if result["verdict"] == "PASS" else 1
            text = json.dumps(result, ensure_ascii=False, indent=2)
            if args.output is not None:
                write_new(args.output, text + "\n")
        elif args.command == "fix":
            result = run_fix(args.input, args.previous, args.fixes)
            code = 0 if result["status"] == "PASS" else 1
            text = json.dumps(result, ensure_ascii=False, indent=2)
            if args.output is not None:
                write_new(args.output, text + "\n")
        else:
            data = load_json(args.contract.read_text(encoding="utf-8-sig"))
            docs = render_documents(data, args.stage)
            for name in docs:
                if (args.output / name).exists() or (args.output / name).is_symlink():
                    raise FileExistsError("Render refuses to overwrite generated documents; use a new output directory")
            args.output.mkdir(parents=True, exist_ok=True)
            created = []
            for name, content in docs.items():
                write_new(args.output / name, content)
                created.append(name)
            findings = validate_contract(data, args.stage)
            result = dict(status="RENDERED", documents=created,
                contract_gate="FAIL" if findings else "NOT_RUN",
                ui_acceptance="UNVERIFIED", findings=findings)
            text = json.dumps(result, ensure_ascii=False, indent=2)
            code = 0
        print(text)
        return code
    except (OSError, ValueError) as exc:
        print(json.dumps(dict(status="ERROR", error=str(exc), ui_acceptance="UNVERIFIED"), ensure_ascii=False))
        return 2

if __name__ == "__main__":
    sys.exit(main())

