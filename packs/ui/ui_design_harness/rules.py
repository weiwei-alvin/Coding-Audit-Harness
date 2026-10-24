"""Deterministic UI anti-slop rule scanner.

Rules are JSON data (default ui_design_harness/data/ui-rules.json); this module
implements three generic match kinds and binds every finding to a stable key and
content hashes. It is a Tier-1 deterministic check: it never renders a page and
never claims UI acceptance.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import re

from jsonschema import Draft202012Validator

from .contract import ROOT, engine_hash, load_json, sha

RULESET_PATH = ROOT / "ui_design_harness/data/ui-rules.json"
RULES_SCHEMA_PATH = ROOT / "schemas/rules.schema.json"
SEVERITIES = ("blocking", "major", "minor")
FAILING_SEVERITIES = ("blocking", "major")
EXTENSIONS = ("html", "css", "js", "jsx", "ts", "tsx", "vue", "svelte")
SKIP_DIRS = {"node_modules", "dist", "build", ".git", ".trail", "outputs", "test-results",
    "__pycache__", ".venv", "venv", "htmlcov"}
MAX_FILE_BYTES = 1024 * 1024
LIMITATIONS = [
    "Regex over static source text only; rendered-state criteria (computed contrast, nested cards, hit targets, heading order) belong to T-002 collectors and T-004 review.",
    "Each file is scanned independently; componentized projects that split labels and inputs across files can trip WIG-004, which is why it stays minor.",
    "Legitimate uses of a banned pattern (for example a gradient inside a chart) are not distinguished; operators adjust severities via --rules.",
    "Distilled rule snapshot pinned to upstream commits observed 2026-10-19; re-distill when the upstreams move.",
    "This scan is not UI acceptance; ui_acceptance stays UNVERIFIED.",
]


def load_ruleset(path=None):
    """Read and validate a ruleset; raise ValueError when it is not usable."""
    source = Path(path) if path is not None else RULESET_PATH
    raw = source.read_bytes()
    data = load_json(raw.decode("utf-8-sig"))
    schema = load_json(RULES_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(data),
        key=lambda e: str(list(e.absolute_path)))
    if errors:
        raise ValueError("Ruleset failed schema validation: " + errors[0].message)
    for rule in data["rules"]:
        for group in ("patterns", "when", "require"):
            for pattern in rule.get(group, []):
                try:
                    re.compile(pattern, re.IGNORECASE)
                except re.error as exc:
                    raise ValueError(f"Rule {rule['id']} has an invalid regex in {group}: {exc}")
    return data


def verdict(findings, rejections):
    """PASS needs no failing finding and no rejection; minors alone still pass."""
    if rejections:
        return "FAIL"
    if any(f["severity"] in FAILING_SEVERITIES for f in findings):
        return "FAIL"
    return "PASS"


def exit_code(status):
    return 0 if status == "PASS" else 1


def _compile(patterns):
    return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


def _line_of(text, index):
    return text.count("\n", 0, index) + 1


def _normalize(match_text):
    return " ".join(match_text.split()).casefold()


def _finding_key(rule_id, relpath, match_text):
    payload = rule_id + "\0" + relpath + "\0" + _normalize(match_text)
    return "F-" + sha(payload.encode("utf-8"))[:16]


def _finding(rule, relpath, locations):
    """One finding per rule+file+normalized match, carrying every occurrence."""
    first_line, first_match = locations[0]
    return dict(rule_id=rule["id"], title=rule["title"], severity=rule["severity"],
        message=rule["message"], remediation=rule["remediation"], file=relpath, line=first_line,
        match=" ".join(first_match.split()),
        locations=[dict(line=line, match=" ".join(text.split())) for line, text in locations],
        finding_key=_finding_key(rule["id"], relpath, first_match), source=dict(rule["source"]))


def _first_match(compiled, text):
    for pattern in compiled:
        match = pattern.search(text)
        if match is not None:
            return match
    return None


def _scan_file(relpath, text, rules):
    findings = []
    extension = relpath.rsplit(".", 1)[-1].lower() if "." in relpath else ""
    for rule in rules:
        if extension not in rule["applies_to"]:
            continue
        kind = rule["kind"]
        if kind == "forbidden":
            hits = {}
            for pattern in _compile(rule["patterns"]):
                for match in pattern.finditer(text):
                    identity = (rule["id"], relpath, _normalize(match.group(0)))
                    hits.setdefault(identity, []).append(
                        (_line_of(text, match.start()), match.group(0)))
            for locations in hits.values():
                findings.append(_finding(rule, relpath, locations))
        elif kind == "required_when":
            trigger = _first_match(_compile(rule["when"]), text)
            if trigger is None:
                continue
            if _first_match(_compile(rule["require"]), text) is not None:
                continue
            findings.append(_finding(rule, relpath,
                [(_line_of(text, trigger.start()), trigger.group(0))]))
        elif kind == "distinct_threshold":
            values = {}
            first = None
            for pattern in _compile(rule["patterns"]):
                for match in pattern.finditer(text):
                    group = match.group(1) if match.groups() else match.group(0)
                    values.setdefault(group.casefold(), group)
                    if first is None:
                        first = match
            if first is not None and len(values) >= rule["threshold"]:
                findings.append(_finding(rule, relpath,
                    [(_line_of(text, first.start()), ", ".join(sorted(values.values())))]))
    return findings


def iter_source_files(target):
    target = Path(target)
    if target.is_file():
        yield target, target.name
        return
    for root, dirs, names in os.walk(target):
        dirs[:] = sorted(d for d in dirs
            if d not in SKIP_DIRS and not (Path(root) / d).is_symlink())
        for name in sorted(names):
            path = Path(root) / name
            if path.is_symlink():
                continue
            yield path, path.relative_to(target).as_posix()


def scan_target(target, ruleset_path=None):
    """Scan a file or directory and return a content-bound report dictionary."""
    ruleset = load_ruleset(ruleset_path)
    rules_source = Path(ruleset_path) if ruleset_path is not None else RULESET_PATH
    rules_digest = sha(rules_source.read_bytes())
    target = Path(target)
    if not target.exists():
        raise FileNotFoundError(f"Scan target does not exist: {target}")

    files, skipped, findings, rejections = [], [], [], []
    for path, relpath in iter_source_files(target):
        extension = relpath.rsplit(".", 1)[-1].lower() if "." in relpath else ""
        if extension not in EXTENSIONS:
            continue
        raw = path.read_bytes()
        if len(raw) > MAX_FILE_BYTES:
            skipped.append(dict(path=relpath, reason="file_too_large"))
            continue
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            skipped.append(dict(path=relpath, reason="not_utf8_text"))
            continue
        files.append(dict(path=relpath, sha256=sha(raw), bytes=len(raw)))
        findings.extend(_scan_file(relpath, text, ruleset["rules"]))

    if not files:
        rejections.append(dict(code="NO_SCANNABLE_FILES", path=target.as_posix(),
            message="No scannable UI source files under the target; an empty scan is not a PASS"))

    findings.sort(key=lambda f: (f["file"], f["line"], f["rule_id"]))
    return dict(schema_version="0.1", kind="ui_rules_scan", status=verdict(findings, rejections),
        scanned_at=datetime.now(timezone.utc).isoformat(), ui_acceptance="UNVERIFIED",
        target=dict(path=target.resolve().as_posix(), files=files, skipped=skipped),
        ruleset=dict(name=ruleset["ruleset"], compiled_at=ruleset["compiled_at"],
            sha256=rules_digest, rule_count=len(ruleset["rules"]),
            rule_ids=sorted(rule["id"] for rule in ruleset["rules"])),
        engine_hash=engine_hash(), findings=findings, rejections=rejections,
        summary=dict(files_scanned=len(files),
            blocking=sum(1 for f in findings if f["severity"] == "blocking"),
            major=sum(1 for f in findings if f["severity"] == "major"),
            minor=sum(1 for f in findings if f["severity"] == "minor"),
            rules_triggered=sorted({f["rule_id"] for f in findings})),
        verification=dict(reproduce=[
            "python -m ui_design_harness rules --input <target> --output <new-receipt>",
        ]),
        limitations=list(LIMITATIONS))
