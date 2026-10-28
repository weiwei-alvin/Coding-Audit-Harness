"""T-010 end-to-end proof: the T-005 real UI case re-run through the unified kernel pipeline.

Same real case (the telling-time game; contract and build are absorbed copies under
packs/ui/examples/e2e-case/, the original stays untouched). One disposable kernel
project inside the new evidence directory walks every gate:

init (entry DISCOVERY) -> DISCOVERY -> SPEC -> DESIGN (gate PASS recorded) ->
TICKETS (dependency hook + T-009 conditional-gate hook; approved plan recorded) ->
guard proof (a state that starts at TICKETS with no gate history is refused and
names the reason) -> IMPLEMENTATION: verify v0 (rules FAIL saved as receipt) ->
PLAN_CHANGE pause probe (SPEC change pauses; decide CONTINUE resumes) ->
FIX_REQUIRED review -> targeted fix -> re-verify (rules PASS, fresh collector
evidence) -> findings resolved -> PASS review with three evidence tiers -> project
COMPLETE at the terminal REVIEW stage -> final gate (rules clean, browser evidence
clean, declared judgment with source and limitations).

New/old cross-check (T-010 checkbox): engine_hash and rendered document hashes from
the absorbed CLI are compared against the T-005 evidence; same bytes, new location,
history untouched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "packs" / "ui"
CLI = PACK / "cli.py"
VYPY = sys.executable  # Use the active interpreter on both Ubuntu and Windows

CASE_CONTRACT = PACK / "examples/e2e-case/contract.json"
CASE_BUILD = PACK / "examples/e2e-case/telling-time.html"
ORIGINAL_SOURCE = Path(r"D:\Educator-Studio\edu-web-games\telling-time\index.html")
STORY = "US-002"

# Same targeted rules from the T-005 run: only the named findings, inside the copied build.
FIX_EDITS = [
    ("background:linear-gradient(90deg,#4f7cff,#7aa2ff)", "background:var(--pri)"),
    ("background:linear-gradient(135deg,#4f7cff,#7b5cff)", "background:var(--pri)"),
    ("#fff", "#fbfcff"),
]
REDUCED_MOTION_BLOCK = "@media (prefers-reduced-motion: reduce){.fb.show{animation:none}}\n</style>"

EXPECTED_ARTIFACTS = [
    "evidence/report.json", "evidence/manifest.json", "evidence/aria-snapshot.yaml",
    "evidence/console.json", "evidence/keyboard.json",
    "evidence/screenshots/desktop.png", "evidence/screenshots/tablet.png",
    "evidence/screenshots/narrow.png", "evidence/screenshots/reduced-motion.png",
    "evidence/screenshots/forced-colors.png",
]

FINAL_LIMITATIONS = [
    "Single real case only; the harness itself is not proven by one case.",
    "Playwright chromium reuses the shared local browser cache; not a cross-browser run.",
    "No real-user or assistive-technology testing; Tier-3 declared judgment covers named criteria only.",
    "The keyboard walkthrough presses Tab a fixed number of times and does not script flows.",
    "Contrast was not measured; forced-colors and reduced-motion are browser emulations.",
]

SPEC_TEXT = "# Spec\n\n## User Stories\n\n1. US-002: 身為學生，我要看到時鐘題目並知道自己答對沒有，才能練習看時間\n"

TICKET_TEXT = """---
id: T-001
depends_on: []
---

# T-001: telling-time 案例走完整條豎切驗收

實作範圍只限案例建置目錄 `game/`（複製品）。規則掃描與瀏覽器證據由 ui-pack typed commands 產生；kernel 收據綁 source_hash。
"""

CHECK_WRAPPER = '''"""ui-pack design gate re-run: prints the check receipt JSON on stdout (no file writes)."""
import subprocess, sys
from pathlib import Path
cmd = [sys.executable, str(Path(r"__REPO__") / "packs/ui/cli.py"),
    "check", "--contract", "contract.json", "--stage", "design", "--documents", "docs"]
r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=300)
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr)
sys.exit(r.returncode)
'''

SCAN_WRAPPER = '''"""ui-pack rules scan: fresh exclusive receipt each run; prints the receipt JSON."""
import subprocess, sys, uuid
from pathlib import Path
out = Path("receipts") / (uuid.uuid4().hex + ".json")
out.parent.mkdir(exist_ok=True)
cmd = [sys.executable, str(Path(r"__REPO__") / "packs/ui/cli.py"),
    "rules", "--input", "game", "--output", str(out)]
r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=300)
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr)
sys.exit(r.returncode)
'''

COLLECT_WRAPPER = '''"""ui-pack browser collector: regenerates the evidence dir in place each run."""
import shutil, subprocess, sys
from pathlib import Path
if Path("evidence").exists():
    shutil.rmtree("evidence")
cmd = [sys.executable, str(Path(r"__REPO__") / "packs/ui/cli.py"),
    "collect", "--input", "game/telling-time.html", "--output", "evidence", "--wait-ms", "80"]
r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=600)
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr)
sys.exit(r.returncode)
'''


def sha_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_case_project(case):
    """Disposable kernel project with the absorbed pack referenced by absolute path."""
    case.mkdir(parents=True)
    shutil.copytree(REPO / "harness", case / "harness",
        ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(PACK, case / "packs/ui",
        ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(CASE_CONTRACT, case / "contract.json")
    (case / "game").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CASE_BUILD, case / "game" / "telling-time.html")
    (case / ".harness").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PACK / "pipeline.json", case / ".harness/pipeline.json")
    write_text(case / "SPEC.md", SPEC_TEXT)
    write_text(case / ".harness/tickets/T-001.md", TICKET_TEXT)
    golden_path = {
        "source_hash_exclude": ["evidence", "receipts"],
        "steps": [
            {"id": "GP-001", "description": "DESIGN 契約檢查重跑（pack check，assertion tier）",
             "user_story_ids": [STORY], "ticket_ids": ["T-001"],
             "verification_command": [VYPY, "scripts/check.py"], "expected_output": ""},
            {"id": "GP-002", "description": "規則掃描（pack rules，assertion tier）",
             "user_story_ids": [STORY], "ticket_ids": ["T-001"],
             "verification_command": [VYPY, "scripts/scan.py"], "expected_output": ""},
            {"id": "GP-003", "description": "瀏覽器證據收集器（pack collect，captured tier）",
             "user_story_ids": [STORY], "ticket_ids": ["T-001"],
             "verification_command": [VYPY, "scripts/collect.py"], "expected_output": "",
             "verification_type": "collector", "expected_artifacts": list(EXPECTED_ARTIFACTS)},
        ],
    }
    write_json(case / ".harness/golden_path.json", golden_path)
    for name, template in (("check.py", CHECK_WRAPPER), ("scan.py", SCAN_WRAPPER), ("collect.py", COLLECT_WRAPPER)):
        write_text(case / "scripts" / name, template.replace("__REPO__", str(REPO).replace("\\", "\\\\")))
    return case


def parse_json(stdout):
    try:
        return json.loads(stdout)
    except ValueError:
        return None


def stdout_of(record_receipt, step_id):
    """One run's step stdout; verification receipts embed results/stdout, the
    kernel's final-verification artifact embeds details/output."""
    for result in (record_receipt or {}).get("results", []):
        if result.get("step_id") == step_id:
            return parse_json(result.get("stdout") or "")
    for result in (record_receipt or {}).get("details", []):
        if result.get("step_id") == step_id:
            return parse_json(result.get("output") or "")
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New evidence directory; existing paths rejected")
    parser.add_argument("--old-evidence", type=Path, default=None,
        help="Optional historical T-005 evidence directory for legacy baseline cross-checks. "
             "When omitted, baseline checks are explicitly NOT_RUN; live E2E checks still execute.")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Use a new output directory")
    old_evidence = args.old_evidence.resolve() if args.old_evidence is not None else None
    if old_evidence is not None and not old_evidence.is_dir():
        parser.error("--old-evidence must point to an existing directory")
    steps_dir = output / "steps"
    steps_dir.mkdir(parents=True)
    case = output / "case"
    results = []

    def record(label, passed, payload=None, command=None, stderr=""):
        entry = dict(id=label, passed=passed, payload=payload, command=command, stderr=stderr)
        write_json(steps_dir / (label + ".json"), entry)
        results.append(entry)
        if not passed:
            save_failed_debug(label, payload, stderr)
        return entry

    def save_failed_debug(label, payload, stderr):
        write_json(steps_dir / (label + "-DEBUG.json"), dict(payload=payload, stderr=stderr))

    cli = [VYPY, str(REPO / "harness/runner/runner.py"), "--project-root", str(case)]
    # Deliberately visible Python-only test injection, not a public CLI bypass.
    approval_entry = (
        "import sys; sys.path.insert(0,sys.argv[1]); from runner import main; "
        "sys.argv=['runner.py']+sys.argv[2:]; "
        "main(confirm_pass=lambda stage, fingerprint: True)"
    )

    def approved_cli(project):
        return [VYPY, "-c", approval_entry, str(REPO / "harness/runner"),
            "--project-root", str(project)]

    def run_cli(label, arguments, expect_zero=True, must_contain=None, python_approval=False):
        command = [*(approved_cli(case) if python_approval else cli), *arguments]
        cp = subprocess.run(command, capture_output=True, text=True,
            encoding="utf-8", timeout=900, cwd=str(case))
        passed = ((cp.returncode == 0) == expect_zero
            and (must_contain is None or must_contain in (cp.stderr + cp.stdout)))
        record(label, passed, dict(returncode=cp.returncode,
            stdout_tail=cp.stdout[-3000:]), command, cp.stderr[-2000:])
        return cp

    state_path = case / ".harness/state.json"

    def read_state():
        return json.loads(state_path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # 0. Case project + rendered contract documents (input to the DESIGN gate).
    # ------------------------------------------------------------------
    build_case_project(case)
    render = subprocess.run([VYPY, str(CLI), "render", "--contract", str(case / "contract.json"),
        "--stage", "design", "--output", str(case / "docs")],
        capture_output=True, text=True, encoding="utf-8", timeout=120)
    render_payload = parse_json(render.stdout)
    record("render-design-documents", render.returncode == 0
        and render_payload and render_payload.get("status") == "RENDERED",
        dict(returncode=render.returncode, documents=(render_payload or {}).get("documents")),
        None, render.stderr)
    design_check = subprocess.run([VYPY, str(CLI), "check", "--contract", str(case / "contract.json"),
        "--stage", "design", "--documents", str(case / "docs"),
        "--receipt", str(case / "design-receipt.json")],
        capture_output=True, text=True, encoding="utf-8", timeout=120)
    design_payload = parse_json(design_check.stdout)
    record("design-receipt-before-gate", design_check.returncode == 0
        and design_payload and design_payload.get("status") == "PASS",
        dict(returncode=design_check.returncode, status=(design_payload or {}).get("status")),
        None, design_check.stderr)

    # ------------------------------------------------------------------
    # 1. Walk every planning gate; DESIGN PASS lands in stage_gates.
    # ------------------------------------------------------------------
    run_cli("init", ["init"])
    for label, expected_stage in (
            ("gate-discovery", "DISCOVERY"), ("gate-spec", "SPEC"), ("gate-design", "DESIGN")):
        state = read_state()
        if state["pipeline_stage"] != expected_stage:
            record("walk-" + label, False, dict(stage=state["pipeline_stage"], expected=expected_stage))
        run_cli("walk-" + label + "-ready", ["set-ready-for-gate"])
        run_cli("walk-" + label + "-pass", ["gate-verdict", "--verdict", "PASS"])
    state = read_state()
    record("stage-gates-recorded", state.get("stage_gates", {}).get("DESIGN") == "PASS"
        and state["pipeline_stage"] == "TICKETS", dict(state_gates=state.get("stage_gates")))

    # ------------------------------------------------------------------
    # 2. T-009 guard: a state at TICKETS without gate history is refused by name.
    # ------------------------------------------------------------------
    jump = output / "guard-jump-case"
    shutil.copytree(case, jump)
    jump_state = read_state()
    jump_state.pop("stage_gates", None)
    write_json(jump / ".harness/state.json", jump_state)
    jump_cli = [VYPY, str(REPO / "harness/runner/runner.py"), "--project-root", str(jump)]
    subprocess.run([*jump_cli, "set-ready-for-gate"], capture_output=True, text=True,
        encoding="utf-8", timeout=120, cwd=str(jump))
    cp = subprocess.run([*approved_cli(jump), "gate-verdict", "--verdict", "PASS"], capture_output=True,
        text=True, encoding="utf-8", timeout=120, cwd=str(jump))
    refused = cp.returncode != 0 and "Conditional stage DESIGN" in cp.stderr \
        and "golden_path_declares_collector" in cp.stderr
    record("guard-jump-to-tickets-refused", refused, dict(returncode=cp.returncode,
        stderr_tail=cp.stderr[-800:]), [*jump_cli, "set-ready-for-gate", "gate-verdict", "--verdict", "PASS"], cp.stderr[-800:])
    shutil.rmtree(jump)

    # Ticket gate: dependency hook + conditional hook both pass; plan approved.
    run_cli("gate-tickets-ready", ["set-ready-for-gate"])
    before_tty = state_path.read_bytes()
    rejected_tty = run_cli("gate-tickets-non-tty-refused",
        ["gate-verdict", "--verdict", "PASS"], expect_zero=False,
        must_contain="TTY_CONFIRMATION_REQUIRED")
    record("gate-tickets-non-tty-no-state-change", rejected_tty.returncode == 23
        and state_path.read_bytes() == before_tty,
        dict(exit_code=rejected_tty.returncode, state_unchanged=state_path.read_bytes() == before_tty))
    run_cli("gate-tickets-pass", ["gate-verdict", "--verdict", "PASS"], python_approval=True)
    state = read_state()
    record("approved-plan-recorded", state.get("approved_plan", {}).get("sha256") is not None
        and state["pipeline_stage"] == "IMPLEMENTATION"
        and state["active_ticket_id"] == "T-001", dict(
            approved_plan=state.get("approved_plan"),
            active_ticket_id=state.get("active_ticket_id")))

    def snapshot():
        cp = subprocess.run([*cli, "snapshot"], capture_output=True, text=True,
            encoding="utf-8", timeout=120, cwd=str(case))
        # source_hash prints a bare hex digest, not JSON; parse_json would return None.
        return cp.stdout.strip() if cp.returncode == 0 else None

    # ------------------------------------------------------------------
    # 3. Verify v0: contract check PASS, rules scan FAIL (blocking findings in the receipt).
    # ------------------------------------------------------------------
    on_enter = read_state()
    record("on-enter-started-first-ticket", on_enter["active_ticket_id"] == "T-001"
        and on_enter["tickets"]["T-001"]["status"] == "IN_PROGRESS", dict(
            active=on_enter.get("active_ticket_id")))
    cp = run_cli("verify-v0", ["verify-ticket", "--ticket", "T-001", "--trust-commands",
        "--timeout", "600"], expect_zero=False)
    # A blocked verify saves its receipt in state but prints nothing on stdout.
    v0_state = read_state()
    v0_receipt_path = (v0_state.get("tickets", {}).get("T-001", {}).get("verification") or {}).get("path")
    v0 = json.loads((case / ".harness" / v0_receipt_path).read_text(encoding="utf-8")) if v0_receipt_path else {}
    rules_v0 = stdout_of(v0, "GP-002")
    check_v0 = stdout_of(v0, "GP-001")
    v0_rule_ok = bool(rules_v0) and rules_v0.get("status") == "FAIL" and {
        "SLOP-001", "SLOP-009", "WIG-002"} <= set(
        (rules_v0.get("summary") or {}).get("rules_triggered", []))
    record("verify-v0-blocked-by-rules", v0_rule_ok and v0.get("all_passed") is False,
        dict(rules_status=(rules_v0 or {}).get("status"),
             contract_check_status=(check_v0 or {}).get("status"),
             rules_triggered=(rules_v0 and rules_v0.get("summary", {}).get("rules_triggered")),
             receipt_all_passed=v0.get("all_passed")))
    design_check_std = check_v0

    # ------------------------------------------------------------------
    # 4. PLAN_CHANGE probe: SPEC change pauses; decision resumes.
    # ------------------------------------------------------------------
    spec = case / "SPEC.md"
    spec.write_text(spec.read_text(encoding="utf-8")
        + "\n## Revision note\n\n- T-010: same case re-run in the unified pipeline; this note is the accepted change.\n",
        encoding="utf-8")
    run_cli("plan-change-verify-pauses", ["verify-ticket", "--ticket", "T-001",
        "--trust-commands", "--timeout", "600"], expect_zero=False)
    state = read_state()
    decision_ref = (state.get("pause") or {}).get("decision_ref", "")
    record("plan-change-pause-and-ref", state["project_status"] == "PAUSED"
        and state["pause"]["reason"] == "PLAN_CHANGE_REQUIRES_DECISION"
        and decision_ref.startswith("DEC-"), dict(pause=state.get("pause")))
    run_cli("decide-plan-change", ["decide", "--option", "CONTINUE", "--rationale",
        "T-010 re-runs the same real case; the SPEC revision note documents the re-run and is accepted as the new approved plan.",
        "--source", "T-010 verify_unified_e2e operator decision"])
    run_cli("resume-after-decision", ["resume"])
    state = read_state()
    record("resumed-after-plan-decision", state["project_status"] == "IN_PROGRESS"
        and state.get("pause") is None, dict(project_status=state["project_status"]))

    # ------------------------------------------------------------------
    # 5. Review round 1: FIX_REQUIRED with the rules findings recorded.
    # ------------------------------------------------------------------
    source_hash_v1 = snapshot()
    record("source-hash-snapshot-1", bool(source_hash_v1), dict(source_hash=source_hash_v1))
    run_cli("mark-ready-for-review-1", ["mark-ticket-ready-for-review", "--ticket", "T-001"])
    round1 = review_record(1, source_hash_v1, workload_findings(rules_v0),
        criteria=dict(GP001="PASS", GP002="FAIL", GP003="PASS"))
    review1_path = case / "receipts" / "review-1.json"
    handoff1_path = case / "receipts" / "handoff-1.json"
    write_json(review1_path, round1)
    write_json(handoff1_path, handoff_record(1, source_hash_v1,
        verification=[dict(step="deferred-until-fix", expected="re-verify after targeted fix",
            actual="fix pending", status="PASS")]))
    run_cli("review-fix-required", ["review-verdict", "--ticket", "T-001", "--verdict",
        "FIX_REQUIRED", "--review", str(review1_path)])
    state = read_state()
    blocking = sorted(fid for fid, f in state["findings"].items() if f.get("blocking", True))
    record("findings-recorded-and-blocking",
        len(state["findings"]) == len(round1["findings"])
        and len(blocking) == sum(1 for f in round1["findings"] if f["blocking"])
        and state["tickets"]["T-001"]["status"] == "IN_PROGRESS",
        dict(findings=blocking, ticket_status=state["tickets"]["T-001"]["status"]))
    attempts = state["tickets"]["T-001"].get("review_total", 1)

    # Targeted fix (real source change, not during verification).
    build = case / "game" / "telling-time.html"
    text = build.read_text(encoding="utf-8")
    edits = []
    for old, new in FIX_EDITS:
        if old == "#fff":
            import re
            text, count = re.subn(r"#fff(?![0-9a-fA-F])", new, text)
        else:
            count = text.count(old)
            text = text.replace(old, new)
        edits.append(dict(old=old, new=new, count=count))
    text = text.replace("</style>", REDUCED_MOTION_BLOCK)
    build.write_text(text, encoding="utf-8")
    record("targeted-fix-applied", all(e["count"] > 0 for e in edits), dict(
        edits=edits, reduced_motion_inserted=REDUCED_MOTION_BLOCK in text))

    # Re-verify on the fixed build; rules PASS and fresh collector evidence.
    run_cli("re-verify-v1", ["verify-ticket", "--ticket", "T-001", "--trust-commands",
        "--timeout", "600"])
    state = read_state()
    receipt = json.loads((case / ".harness" / state["tickets"]["T-001"]["verification"]["path"])
        .read_text(encoding="utf-8"))
    record("re-verify-all-passed", receipt["all_passed"], dict(
        evidence_tiers=receipt["evidence_tiers"], verification_id=receipt["verification_id"],
        source_hash=receipt["source_hash"]))
    rules_v1 = stdout_of(receipt, "GP-002")
    design_check_v1 = stdout_of(receipt, "GP-001")

    # Final contract basis gate: this content-bound receipt is mandatory for REVIEW PASS.
    final_check = subprocess.run([VYPY, str(CLI), "check", "--contract", str(case / "contract.json"),
        "--stage", "final", "--documents", str(case / "docs"),
        "--receipt", str(case / "receipts/final-receipt.json")],
        capture_output=True, text=True, encoding="utf-8", timeout=120)
    final_check_payload = parse_json(final_check.stdout)
    record("final-contract-basis-receipt", final_check.returncode == 0
        and final_check_payload and final_check_payload.get("status") == "PASS",
        dict(returncode=final_check.returncode, findings=(final_check_payload or {}).get("findings")),
        None, final_check.stderr)

    # Resolve every blocking finding, then PASS review with the three tiers.
    for fid in blocking:
        run_cli("resolve-" + fid, ["resolve-finding", "--finding-id", fid])
    source_hash_v2 = snapshot()
    record("source-hash-snapshot-2", bool(source_hash_v2), dict(source_hash=source_hash_v2))
    run_cli("mark-ready-for-review-2", ["mark-ticket-ready-for-review", "--ticket", "T-001"])
    round2 = review_record(2, source_hash_v2, [], verification_id=receipt["verification_id"],
        criteria=dict(GP001="PASS", GP002="PASS", GP003="PASS", FINAL_INTEGRATION="PASS"),
        source="verify_unified_e2e operator declared judgment on kernel verification "
            + receipt["verification_id"],
        limitations="；".join(FINAL_LIMITATIONS))
    review2_path = case / "receipts" / "review-2.json"
    handoff2_path = case / "receipts" / "handoff-2.json"
    write_json(review2_path, round2)
    write_json(handoff2_path, handoff_record(2, source_hash_v2,
        verification_id=receipt["verification_id"],
        verification=[dict(step="GP-001", expected="design gate PASS", actual="PASS", status="PASS"),
                      dict(step="GP-002", expected="rules PASS", actual="PASS", status="PASS"),
                      dict(step="GP-003", expected="collector PASS", actual="PASS", status="PASS")]))
    before_final_tty = state_path.read_bytes()
    rejected_final = run_cli("final-review-non-tty-refused",
        ["review-verdict", "--ticket", "T-001", "--verdict", "PASS",
         "--trust-commands", "--timeout", "600",
         "--review", str(review2_path), "--handoff", str(handoff2_path)],
        expect_zero=False, must_contain="TTY_CONFIRMATION_REQUIRED")
    record("final-review-non-tty-no-state-change", rejected_final.returncode == 23
        and state_path.read_bytes() == before_final_tty,
        dict(exit_code=rejected_final.returncode,
             state_unchanged=state_path.read_bytes() == before_final_tty))
    run_cli("review-pass", ["review-verdict", "--ticket", "T-001", "--verdict", "PASS",
        "--trust-commands", "--timeout", "600",
        "--review", str(review2_path), "--handoff", str(handoff2_path)], python_approval=True)
    state = read_state()
    record("project-complete-at-review", state["project_status"] == "COMPLETE"
        and state["pipeline_stage"] == "REVIEW", dict(
            project_status=state["project_status"], pipeline_stage=state["pipeline_stage"],
            stage_gates=state.get("stage_gates")))

    # ------------------------------------------------------------------
    # 6. Final gate + old/new cross-checks.
    # ------------------------------------------------------------------
    final_artifact = json.loads((case / ".harness" / state["final_verification"]["path"]).read_text(encoding="utf-8"))
    rules_final = stdout_of(final_artifact, "GP-002")
    check_final = stdout_of(final_artifact, "GP-001")
    collector_final = parse_json((case / "evidence" / "report.json").read_text(encoding="utf-8"))
    old_design = parse_json((old_evidence / "design-receipt.json").read_text(encoding="utf-8")) if old_evidence else None
    old_gate = parse_json((old_evidence / "final-gate.json").read_text(encoding="utf-8")) if old_evidence else None
    new_build_sha = sha_of(case / "game" / "telling-time.html")
    cross = dict(
        engine_hash_match=(bool(check_final) and check_final.get("engine_hash") == (old_design or {}).get("engine_hash")) if old_evidence else None,
        document_hashes_match=(bool(check_final) and check_final.get("document_hashes") == (old_design or {}).get("document_hashes")) if old_evidence else None,
        build_sha256_match=(bool(old_gate) and new_build_sha == old_gate.get("build_sha256")) if old_evidence else None)

    def has(record_payload, *keys):
        return all(record_payload is not None and record_payload.get(k) is not None for k in keys)

    unresolved = state["findings"] and any(
        f["status"] in ("OPEN", "REOPENED") and f.get("blocking", True) for f in state["findings"].values())
    gate = dict(kind="ui_final_gate", passed=False, ui_acceptance="UNVERIFIED",
        historical_baseline="CHECKED" if old_evidence else "NOT_RUN",
        checks=[
            dict(id="stage-gates-walked", passed=state.get("stage_gates", {}).get("DESIGN") == "PASS"),
            dict(id="kernel-final-integrated", passed=(final_artifact or {}).get("status") == "PASSED"),
            dict(id="rules-scan", passed=bool(rules_final) and rules_final["status"] == "PASS"
                and rules_final["findings"] == []),
            dict(id="contract-check", passed=bool(check_final) and check_final["status"] == "PASS"),
            dict(id="browser-evidence", passed=bool(collector_final)
                and collector_final["status"] == "PASS"
                and collector_final["console"]["errors"] == 0
                and collector_final["keyboard"]["operable_reached"] > 0),
            dict(id="three-tiers", passed=all(
                tier in receipt["evidence_tiers"] for tier in ("deterministic", "captured"))),
            dict(id="declared-judgment", passed=bool(round2["criteria"][-1].get("source"))
                and bool(round2["criteria"][-1].get("limitations"))),
            dict(id="no-unresolved-blocking-findings", passed=not unresolved),
        ] + ([
            dict(id="engine-hash-cross-check", passed=cross["engine_hash_match"]),
            dict(id="document-hash-cross-check", passed=cross["document_hashes_match"]),
            dict(id="build-sha-cross-check", passed=cross["build_sha256_match"]),
        ] if old_evidence else []),
        build_sha256=new_build_sha,
        cross_check=cross,
        limitations=FINAL_LIMITATIONS)
    gate["ui_acceptance"] = "VERIFIED" if all(c["passed"] for c in gate["checks"]) else "UNVERIFIED"
    gate["passed"] = gate["ui_acceptance"] == "VERIFIED"
    write_json(output / "final-gate.json", gate)
    record("final-gate-verdict", gate["passed"], gate)

    summary = dict(
        status="PASS" if all(r["passed"] for r in results) else "FAIL",
        kind="t010_unified_e2e_evidence", ticket="T-010 / Ticket-07 P3",
        case=dict(name="Telling the Time 英文報時大挑戰",
            original_source_sha256=sha_of(ORIGINAL_SOURCE) if ORIGINAL_SOURCE.exists() else None,
            contract_sha256=sha_of(CASE_CONTRACT), story=STORY,
            convention_note="case contract/build are absorbed copies under packs/ui/examples/e2e-case/"),
        walk=dict(entry="DISCOVERY", stage_gates=state.get("stage_gates"),
            pipeline_terminal=state["pipeline_stage"], project_status=state["project_status"]),
        final_gate=dict(ui_acceptance=gate["ui_acceptance"], passed=gate["passed"],
            unresolved_blocking_major=bool(unresolved)),
        new_old_cross_check=cross,
        historical_baseline=gate["historical_baseline"],
        review_attempts=dict(fix_round_attempts=attempts),
        cli_cases=len(results), cli_passed=sum(r["passed"] for r in results),
        ui_e2e=gate["ui_acceptance"],
        evidence_directory=str(output),
        results=[dict(id=r["id"], passed=r["passed"]) for r in results])
    write_json(output / "summary.json", summary)

    manifest = dict(schema_version="0.1", kind="t010_unified_e2e_manifest",
        command=[sys.executable, str(Path(__file__))] + sys.argv[1:],
        artifacts=[dict(path=p.relative_to(output).as_posix(), sha256=sha_of(p), bytes=p.stat().st_size)
            for p in sorted(output.rglob("*")) if p.is_file()
            and p.name not in ("manifest.json", "summary.json")],
        ui_acceptance=gate["ui_acceptance"])
    write_json(output / "manifest.json", manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


def review_record(round_no, source_hash_value, findings, criteria, verification_id=None,
                  source=None, limitations=None):
    """Review payload bound to the ticket snapshot; declared criteria carry source/limits."""
    tier_map = dict(GP001="deterministic", GP002="deterministic", GP003="captured")
    items = []
    for key, status in criteria.items():
        item = dict(id={"GP001": "GP-001", "GP002": "GP-002", "GP003": "GP-003",
            "FINAL_INTEGRATION": "FINAL_INTEGRATION"}[key], status=status, critical=True,
            tier=tier_map.get(key, "declared"),
            evidence="kernel receipt step " + {"GP001": "GP-001", "GP002": "GP-002", "GP003": "GP-003"}.get(key, "FINAL_INTEGRATION"))
        if item["tier"] == "declared":
            item["source"] = source or "verify_unified_e2e operator"
            item["limitations"] = limitations or "named criteria only"
        items.append(item)
    payload = dict(review_round=round_no,
        ticket_id="T-001", verdict="FIX_REQUIRED" if findings else "PASS",
        criteria=items, findings=findings, source_hash=source_hash_value)
    if verification_id:
        payload["verification_id"] = verification_id
    return payload


def handoff_record(round_no, source_hash_value, verification_id=None, verification=None):
    handoff = dict(review_round=round_no,
        ticket_id="T-001", source_hash=source_hash_value,
        changes=[dict(file="game/telling-time.html", summary="decorative gradients replaced, reduced-motion block added")],
        verification=verification or [], dependencies=[])
    if verification_id:
        handoff["verification_id"] = verification_id
    return handoff


def workload_findings(rules_receipt):
    """Rules findings become blocking review findings with finding keys."""
    import re
    items = []
    for finding in (rules_receipt or {}).get("findings", []):
        key = re.sub(r"[^a-z0-9\-]", "-", finding["finding_key"].lower()) or "rules-finding"
        items.append(dict(finding_key=key, criterion_ref="GP-002",
            description=finding["rule_id"] + " " + finding["title"]
                + "（" + str(len(finding["locations"])) + " 處）",
            blocking=finding.get("severity") != "minor"))
    return items


if __name__ == "__main__":
    sys.exit(main())
