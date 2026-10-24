"""Review/fix runtime over T-001 rule receipts and T-002 browser evidence.

The rules receipt is the authority on what is currently violated; manual findings
are operator-declared Tier-2/Tier-3 observations. The runtime computes finding
statuses, attempts, verdicts and candidacy, and gates fixes to the scope of the
findings they address. It never claims UI acceptance.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .contract import ROOT, engine_hash, load_json, sha, unresolved
from .rules import iter_source_files

REVIEW_SCHEMA_PATH = ROOT / "schemas/review.schema.json"
DEFAULT_RETRY_LIMIT = 3
RESOLVING_SEVERITIES = ("blocking", "major")
UNRESOLVED_STATUSES = ("OPEN", "PERSISTENT", "REOPENED")
SEVERITY_RANK = {"blocking": 0, "major": 1, "minor": 2}
LIMITATIONS = [
    "The rules receipt is authoritative for rules-sourced findings; manual findings are operator-declared and their resolution cannot be machine-verified.",
    "Scope is the evidence location recorded per finding; cross-file dependencies must be declared by the operator, not inferred.",
    "Design-change decisions are recorded, not approved; authorization semantics belong to the P2 kernel gate/decide.",
    "The review does not read the UI contract; contract freshness is guarded by the guidance flow.",
    "ui_acceptance stays UNVERIFIED here; three complete tiers only produce candidacy, and VERIFIED is T-005's final gate.",
]


def build_fingerprint(target):
    """Per-file SHA-256 plus an aggregate digest for a build directory."""
    target = Path(target)
    if not target.exists():
        raise FileNotFoundError(f"Build target does not exist: {target}")
    files = []
    for path, relpath in iter_source_files(target):
        raw = path.read_bytes()
        files.append(dict(path=relpath, sha256=sha(raw), bytes=len(raw)))
    files.sort(key=lambda entry: entry["path"])
    digest = sha(json.dumps(files, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8"))
    return dict(digest=digest, file_count=len(files), files=files)


def load_review_record(path):
    """Read and schema-validate a review record; raise ValueError when unusable."""
    raw = Path(path).read_bytes()
    data = load_json(raw.decode("utf-8-sig"))
    schema = load_json(REVIEW_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(data),
        key=lambda e: str(list(e.absolute_path)))
    if errors:
        raise ValueError("Review record failed schema validation: " + errors[0].message)
    return data


def _read_json(path):
    return load_json(Path(path).read_text(encoding="utf-8-sig"))


def _verified_evidence(path, expected_sha, label, rejections):
    path = Path(path)
    if not path.is_file():
        rejections.append(dict(code="EVIDENCE_MISSING", path=str(path),
            message=f"{label} evidence file does not exist"))
        return None
    raw = path.read_bytes()
    if sha(raw) != expected_sha:
        rejections.append(dict(code="EVIDENCE_STALE", path=str(path),
            message=f"{label} evidence does not match the hash declared in the record"))
        return None
    try:
        data = _read_json(path)
    except ValueError:
        rejections.append(dict(code="EVIDENCE_INVALID", path=str(path),
            message=f"{label} evidence is not valid JSON"))
        return None
    return data


def _declared_problems(declared):
    problems = []
    for index, entry in enumerate(declared):
        for field in ("criterion", "source", "limitations", "judgment"):
            if unresolved(entry.get(field, "")):
                problems.append(dict(code="DECLARED_INCOMPLETE", path=f"/tiers/declared/{index}/{field}",
                    message="Declared judgment criteria need a real source and limitations"))
    return problems


def _collect_findings(record, receipt, manifest, rejections):
    """Receipt findings are authoritative; record findings annotate or add manual ones."""
    receipt_findings = {}
    if receipt is not None:
        for finding in receipt.get("findings", []):
            receipt_findings[finding["finding_key"]] = finding
    artifacts = set()
    if manifest is not None:
        artifacts = {entry["path"] for entry in manifest.get("artifacts", [])}

    annotations = {}
    for finding in record["findings"]:
        if finding["source"] == "rules":
            if finding["finding_key"] not in receipt_findings:
                rejections.append(dict(code="EVIDENCE_REF_UNRESOLVED",
                    path=finding["finding_key"],
                    message="Record cites a finding key that the rules receipt does not contain"))
                continue
            annotations[finding["finding_key"]] = finding
        else:
            if finding["evidence_ref"] not in artifacts:
                rejections.append(dict(code="EVIDENCE_REF_UNRESOLVED",
                    path=finding["evidence_ref"],
                    message="Manual finding cites an artifact missing from the collector manifest"))
                continue
            annotations[finding["finding_key"]] = finding

    collected = []
    for key, ref in receipt_findings.items():
        note = annotations.get(key, {})
        collected.append(dict(finding_key=key, source="rules", severity=ref["severity"],
            summary=note.get("summary") or f"收據違規未在 review 記錄中列明：{ref['rule_id']}",
            scope_files=[ref["file"]], rule_id=ref.get("rule_id"),
            disposition=note.get("disposition"), disposition_rationale=note.get("disposition_rationale")))
    for finding in record["findings"]:
        if finding["source"] != "manual" or finding["finding_key"] not in annotations:
            continue
        if annotations[finding["finding_key"]] is not finding:
            continue
        collected.append(dict(finding_key=finding["finding_key"], source="manual",
            severity=finding["severity"], summary=finding["summary"],
            scope_files=list(finding["scope_files"]), rule_id=None,
            disposition=finding.get("disposition"),
            disposition_rationale=finding.get("disposition_rationale")))

    for finding in collected:
        if finding["severity"] == "minor" and not (finding["disposition"]
                and finding["disposition_rationale"]):
            rejections.append(dict(code="MINOR_UNDISPOSITIONED", path=finding["finding_key"],
                message="A minor finding that remains needs a disposition and a concrete rationale"))
    return collected


def _statuses(collected, previous, build_changed):
    """Compute per-finding status and attempts against the previous round."""
    previous_map = {}
    if previous is not None:
        previous_map = {f["finding_key"]: f for f in previous.get("findings", [])}
    current_keys = {f["finding_key"] for f in collected}
    result = {}
    for finding in collected:
        key = finding["finding_key"]
        prior = previous_map.get(key)
        if prior is None:
            status, attempts = "OPEN", 1
        elif not build_changed:
            status, attempts = prior["status"], prior["attempts"]
        elif prior["status"] == "RESOLVED":
            status, attempts = "REOPENED", prior["attempts"] + 1
        elif prior["status"] in UNRESOLVED_STATUSES:
            status, attempts = "PERSISTENT", prior["attempts"] + 1
        else:
            status, attempts = "OPEN", 1
        result[key] = dict(status=status, attempts=attempts)
    for key, prior in previous_map.items():
        if key not in current_keys and prior["status"] in UNRESOLVED_STATUSES:
            result[key] = dict(status="RESOLVED", attempts=prior["attempts"])
    return result


def run_review(build, record_path, previous=None, retry_limit=DEFAULT_RETRY_LIMIT):
    """Review one build against its evidence and the previous round."""
    record = load_review_record(record_path)
    rejections = []

    receipt = _verified_evidence(record["evidence"]["rules_receipt"]["path"],
        record["evidence"]["rules_receipt"]["sha256"], "rules_receipt", rejections)
    manifest = _verified_evidence(record["evidence"]["collector_manifest"]["path"],
        record["evidence"]["collector_manifest"]["sha256"], "collector_manifest", rejections)

    prior_report = None
    if previous is not None:
        prior_report = _read_json(previous)
        if prior_report.get("kind") != "ui_review":
            raise ValueError("Previous report is not a ui_review report")

    fingerprint = build_fingerprint(build)
    if not fingerprint["file_count"]:
        rejections.append(dict(code="BUILD_EMPTY", path=str(build),
            message="The build has no scannable source files; an empty review is not a PASS"))

    collected = _collect_findings(record, receipt, manifest, rejections)
    statuses = _statuses(collected, prior_report,
        build_changed=prior_report is None or prior_report["build"]["digest"] != fingerprint["digest"])

    findings = []
    for finding in collected:
        state = statuses[finding["finding_key"]]
        entry = dict(finding, status=state["status"], attempts=state["attempts"])
        findings.append(entry)
    for key, state in statuses.items():
        if state["status"] == "RESOLVED" and key not in {f["finding_key"] for f in findings}:
            prior = {f["finding_key"]: f for f in (prior_report or {}).get("findings", [])}[key]
            findings.append(dict(prior, status="RESOLVED", attempts=state["attempts"]))
    findings.sort(key=lambda f: (SEVERITY_RANK[f["severity"]], f["finding_key"]))

    unresolved_keys = [f["finding_key"] for f in findings
        if f["status"] in UNRESOLVED_STATUSES and f["severity"] in RESOLVING_SEVERITIES]
    paused_keys = [f["finding_key"] for f in findings
        if f["status"] in UNRESOLVED_STATUSES and f["attempts"] >= retry_limit]

    tiers = record["tiers"]
    if receipt is not None:
        receipt_failing = any(f["severity"] in RESOLVING_SEVERITIES
            for f in receipt.get("findings", []))
        expected = "fail" if receipt_failing else "pass"
        if tiers["deterministic"]["status"] != expected:
            rejections.append(dict(code="TIER_INCONSISTENT", path="/tiers/deterministic",
                message=f"Deterministic tier says {tiers['deterministic']['status']} but the receipt implies {expected}"))
    rejections.extend(_declared_problems(tiers["declared"]))

    if rejections:
        verdict = "REJECTED"
    elif paused_keys:
        verdict = "PAUSED"
    elif unresolved_keys:
        verdict = "FIX_REQUIRED"
    else:
        verdict = "PASS"

    candidate_blockers = []
    if verdict == "PASS":
        if tiers["deterministic"]["status"] != "pass":
            candidate_blockers.append(dict(code="DETERMINISTIC_NOT_PASS",
                message="Tier-1 deterministic checks have not passed"))
        if tiers["captured"]["status"] != "reviewed":
            candidate_blockers.append(dict(code="CAPTURED_NOT_REVIEWED",
                message="Tier-2 captured evidence has not been reviewed by a named reviewer"))
        if not tiers["declared"]:
            candidate_blockers.append(dict(code="DECLARED_MISSING",
                message="Tier-3 declared judgment criteria are missing"))

    report = dict(schema_version="0.1", kind="ui_review",
        status="PASS" if verdict == "PASS" else "FAIL", verdict=verdict,
        review_round=record["review_round"], reviewer=record["reviewer"],
        reviewed_at=datetime.now(timezone.utc).isoformat(), ui_acceptance="UNVERIFIED",
        previous_round=prior_report["review_round"] if prior_report else None,
        retry_limit=retry_limit, build=fingerprint,
        findings=findings, unresolved_keys=unresolved_keys,
        decision_required=paused_keys if verdict == "PAUSED" else [],
        tiers=tiers, ui_acceptance_candidate=verdict == "PASS" and not candidate_blockers,
        candidate_blockers=candidate_blockers, rejections=rejections,
        evidence=dict(
            rules_receipt=dict(path=record["evidence"]["rules_receipt"]["path"],
                sha256=record["evidence"]["rules_receipt"]["sha256"]),
            collector_manifest=dict(path=record["evidence"]["collector_manifest"]["path"],
                sha256=record["evidence"]["collector_manifest"]["sha256"])),
        engine_hash=engine_hash(),
        verification=dict(reproduce=[
            "python -m ui_design_harness rules --input <build> --output <rules-receipt>",
            "python -m ui_design_harness collect --input <build/page.html> --output <evidence-directory>",
            "python -m ui_design_harness review --input <build> --record <review.json> --previous <previous-report.json>",
        ]),
        limitations=list(LIMITATIONS))
    return report


def run_fix(build, previous_report_path, fixes_path):
    """Check that a fix stays inside the scope of the findings it addresses."""
    previous = _read_json(previous_report_path)
    if previous.get("kind") != "ui_review":
        raise ValueError("Previous report is not a ui_review report")
    fixes = _read_json(fixes_path)
    if not isinstance(fixes.get("addressed"), list):
        raise ValueError("Fixes file needs an addressed list of finding keys")
    design_change = fixes.get("design_change") or {}
    if not isinstance(design_change, dict):
        raise ValueError("design_change must be an object")

    new_fingerprint = build_fingerprint(build)
    if not new_fingerprint["file_count"]:
        raise ValueError("The fixed build has no scannable source files")

    old_files = {entry["path"]: entry["sha256"] for entry in previous["build"]["files"]}
    new_files = {entry["path"]: entry["sha256"] for entry in new_fingerprint["files"]}
    changed = sorted(set(old_files) ^ set(new_files)
        | {p for p in set(old_files) & set(new_files) if old_files[p] != new_files[p]})

    previous_findings = {f["finding_key"]: f for f in previous.get("findings", [])}
    addressed = list(fixes["addressed"])
    unknown = [key for key in addressed if key not in previous_findings
        or previous_findings[key]["status"] not in UNRESOLVED_STATUSES]

    if new_fingerprint["digest"] == previous["build"]["digest"]:
        verdict = "NO_CONTENT_CHANGE"
    elif unknown:
        verdict = "UNKNOWN_FINDING"
    elif design_change.get("requested"):
        if unresolved(str(design_change.get("rationale", ""))):
            verdict = "DESIGN_CHANGE_INVALID"
        else:
            verdict = "DESIGN_CHANGE_DECLARED"
    else:
        scope = sorted({p for key in addressed if key in previous_findings
            for p in previous_findings[key]["scope_files"]})
        out_of_scope = [p for p in changed if p not in scope]
        verdict = "SCOPE_VIOLATION" if out_of_scope else "APPROVED_SCOPE"

    scope = sorted({p for key in addressed if key in previous_findings
        for p in previous_findings[key]["scope_files"]})
    return dict(schema_version="0.1", kind="ui_fix",
        status="PASS" if verdict in ("APPROVED_SCOPE", "DESIGN_CHANGE_DECLARED") else "FAIL",
        verdict=verdict, previous_round=previous["review_round"],
        addressed=addressed, unknown_findings=unknown, changed_files=changed,
        scope_files=scope,
        out_of_scope_files=[p for p in changed if p not in scope] if verdict == "SCOPE_VIOLATION" else [],
        design_change=dict(requested=bool(design_change.get("requested")),
            rationale=str(design_change.get("rationale", "")),
            scope_files=list(design_change.get("scope_files", []))) if design_change.get("requested") else None,
        build=new_fingerprint, ui_acceptance="UNVERIFIED",
        verification=dict(reproduce=[
            "python -m ui_design_harness fix --input <fixed-build> --previous <previous-report.json> --fixes <fixes.json>",
        ]),
        limitations=list(LIMITATIONS))
