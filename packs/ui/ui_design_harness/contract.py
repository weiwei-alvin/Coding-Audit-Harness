"""Fail-closed checks of UI contracts, not a visual or usability judge."""
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/contract.schema.json"
STATE_KINDS = {"default", "loading", "empty", "error", "success", "validation_error", "disabled"}
REVIEW_CATEGORIES = {"art_direction", "design_system", "anti_generic", "responsive", "accessibility"}
PLACEHOLDERS = {"unknown", "tbd", "todo", "待補", "未定", "待確認", "?", "待填"}
STAGES = {"discovery", "design"}

def unresolved(value):
    return not value.strip() or value.strip().casefold() in PLACEHOLDERS or "{{" in value or "}}" in value

def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result

def load_json(text):
    def reject_constant(value):
        raise ValueError(f"Non-JSON constant: {value}")
    return json.loads(text, object_pairs_hook=_unique_pairs, parse_constant=reject_constant)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def _add(findings, code, path, message):
    findings.append(dict(code=code, path=path, message=message))

def _schema_errors(data, stage):
    if stage not in STAGES:
        raise ValueError(f"Unsupported stage: {stage}")
    schema = load_json(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    # A partly drafted later stage cannot prevent checking completed discovery.
    active = {k: v for k, v in data.items() if stage == "design" or k not in {"spec", "design"}} if isinstance(data, dict) else data
    findings = [
        dict(code="SCHEMA", path="/" + "/".join(map(str, e.absolute_path)), message=e.message)
        for e in sorted(Draft202012Validator(schema).iter_errors(active), key=lambda e: str(list(e.absolute_path)))
    ]
    if isinstance(data, dict) and stage == "design":
        for name in ("spec", "design"):
            if name not in data:
                _add(findings, "SECTION_REQUIRED", "/" + name, f"{name} is required at the design gate")
    return findings

def validate_contract(data, stage):
    findings = _schema_errors(data, stage)
    if findings:
        return findings

    def add(code, path, message):
        _add(findings, code, path, message)

    def known(value, path=""):
        if isinstance(value, dict):
            for key, child in value.items():
                if stage == "discovery" and path == "" and key in {"spec", "design"}:
                    continue
                known(child, path + "/" + key)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                known(child, f"{path}/{i}")
            if value and all(isinstance(x, str) for x in value) and len(value) != len(set(value)):
                add("DUPLICATE_REFERENCE", path, "A list repeats a value")
        elif isinstance(value, str):
            if re.fullmatch(r"/brief/unknowns/[0-9]+/resolution", path):
                return
            if unresolved(value):
                add("UNRESOLVED_VALUE", path, "Required content has an unresolved value")

    known(data)
    for key in ("established_date", "updated_date"):
        try:
            date.fromisoformat(data["metadata"][key])
        except ValueError:
            add("INVALID_DATE", "/metadata/" + key, "Use a real calendar date")
    if data["metadata"]["updated_date"] < data["metadata"]["established_date"]:
        add("INVALID_DATE", "/metadata", "updated_date precedes established_date")

    def index(items, path):
        result = {}
        for item in items:
            if item["id"] in result:
                add("DUPLICATE_ID", path, f"Duplicate ID {item['id']}")
            result[item["id"]] = item
        return result

    def refs(values, table, path):
        for value in values:
            if value not in table:
                add("REFERENCE_UNKNOWN", path, f"Unknown reference {value}")

    b = data["brief"]
    users = index(b["users"], "/brief/users")
    tasks = index(b["tasks"], "/brief/tasks")
    objects = index(b["objects"], "/brief/objects")
    flows = index(b["flows"], "/brief/flows")
    index(b["success_criteria"], "/brief/success_criteria")
    index(b["unknowns"], "/brief/unknowns")
    for u in users.values():
        refs(u["task_ids"], tasks, u["id"])
        actual = {t["id"] for t in tasks.values() if t["user_id"] == u["id"]}
        if actual != set(u["task_ids"]):
            add("TRACEABILITY", u["id"], "User task_ids and task ownership disagree")
    for t in tasks.values():
        refs([t["user_id"]], users, t["id"])
        refs([t["flow_id"]], flows, t["id"])
        if t["flow_id"] in flows and flows[t["flow_id"]]["task_id"] != t["id"]:
            add("TRACEABILITY", t["id"], "Task and flow disagree")
    for f in flows.values():
        refs([f["task_id"]], tasks, f["id"])
        if f["task_id"] in tasks and tasks[f["task_id"]]["flow_id"] != f["id"]:
            add("TRACEABILITY", f["id"], "Flow and task disagree")
    if b["data_density"]["maximum_records"] < b["data_density"]["typical_records"]:
        add("DATA_DENSITY", "/brief/data_density", "Maximum records must cover typical records")
    for q in b["unknowns"]:
        resolved = q["resolution"].strip()
        if q["blocking"] and unresolved(resolved):
            add("BLOCKING_UNKNOWN", q["id"], "Resolve the blocking discovery question before proceeding")
    if stage == "discovery":
        return findings

    s, d = data["spec"], data["design"]
    stories = index(s["stories"], "/spec/stories")
    screens = index(s["screens"], "/spec/screens")
    acs = index(s["acceptance_criteria"], "/spec/acceptance_criteria")
    successes = {item["id"] for item in b["success_criteria"]}
    ia = s["information_architecture"]
    refs([ia["entry_screen_id"]], screens, "/spec/information_architecture")
    nav = {}
    for node in ia["navigation"]:
        sid, parent = node["screen_id"], node["parent_screen_id"]
        refs([sid], screens, "/spec/information_architecture/navigation")
        if parent is not None:
            refs([parent], screens, sid)
        if sid in nav:
            add("IA_DUPLICATE", sid, "Screen occurs twice in navigation")
        nav[sid] = parent
    if set(nav) != set(screens):
        add("IA_COVERAGE", "/spec/information_architecture", "Navigation must cover every screen")
    if {sid for sid, parent in nav.items() if parent is None} != {ia["entry_screen_id"]}:
        add("IA_ROOT", "/spec/information_architecture", "Only the entry screen may be a navigation root")
    for sid in nav:
        seen, current = set(), sid
        while current is not None and current in nav:
            if current in seen:
                add("IA_CYCLE", sid, "Navigation has a parent cycle")
                break
            seen.add(current)
            current = nav[current]
    states_by_screen = {}
    for screen in screens.values():
        refs(screen["flow_ids"], flows, screen["id"])
        refs(screen["object_ids"], objects, screen["id"])
        kinds = [x["kind"] for x in screen["states"]]
        excluded = [x["kind"] for x in screen["state_exclusions"]]
        states_by_screen[screen["id"]] = set(kinds)
        if len(kinds) != len(set(kinds)) or len(excluded) != len(set(excluded)):
            add("DUPLICATE_STATE", screen["id"], "A screen state or exclusion is repeated")
        if set(kinds) & set(excluded):
            add("STATE_CONFLICT", screen["id"], "An applicable state is also excluded")
        if (set(kinds) | set(excluded)) != STATE_KINDS or "default" not in kinds:
            add("STATE_COVERAGE", screen["id"], "Define default and explicitly cover or exclude every remaining state")
        if not any(screen["id"] in st["screen_ids"] for st in stories.values()):
            add("SCREEN_COVERAGE", screen["id"], "No user story owns this screen")
        for kind in kinds:
            if not any(a["screen_id"] == screen["id"] and a["state"] == kind and a["required"] for a in acs.values()):
                add("AC_COVERAGE", screen["id"] + "/" + kind, "No required UI-AC covers this state")
    for st in stories.values():
        refs(st["success_criteria_ids"], successes, st["id"])
        refs([st["user_id"]], users, st["id"])
        refs([st["task_id"]], tasks, st["id"])
        refs(st["screen_ids"], screens, st["id"])
        refs(st["ac_ids"], acs, st["id"])
        if st["task_id"] in tasks:
            task = tasks[st["task_id"]]
            if task["user_id"] != st["user_id"]:
                add("TRACEABILITY", st["id"], "Story and task users disagree")
            for sid in st["screen_ids"]:
                if sid in screens and task["flow_id"] not in screens[sid]["flow_ids"]:
                    add("TRACEABILITY", st["id"], "Story screen does not support its task flow")
        actual = {a["id"] for a in acs.values() if a["story_id"] == st["id"]}
        if actual != set(st["ac_ids"]):
            add("TRACEABILITY", st["id"], "Story ac_ids and UI-AC ownership disagree")
    for a in acs.values():
        refs([a["story_id"]], stories, a["id"])
        refs([a["screen_id"]], screens, a["id"])
        if a["screen_id"] in screens and a["state"] not in states_by_screen[a["screen_id"]]:
            add("AC_STATE", a["id"], "UI-AC references an inapplicable screen state")
        if a["story_id"] in stories and a["screen_id"] not in stories[a["story_id"]]["screen_ids"]:
            add("TRACEABILITY", a["id"], "UI-AC screen is not owned by its story")
    for tid in tasks:
        if not any(st["task_id"] == tid for st in stories.values()):
            add("TASK_COVERAGE", tid, "No user story covers this task")
    for success in successes:
        if not any(success in st["success_criteria_ids"] for st in stories.values()):
            add("SUCCESS_COVERAGE", success, "No user story covers this success criterion")
    for fid in flows:
        if not any(fid in sc["flow_ids"] for sc in screens.values()):
            add("FLOW_COVERAGE", fid, "No screen covers this flow")
    for oid in objects:
        if not any(oid in sc["object_ids"] for sc in screens.values()):
            add("OBJECT_COVERAGE", oid, "No screen represents this object")

    tokens = index(d["tokens"], "/design/tokens")
    components = index(d["components"], "/design/components")
    responsive = index(d["responsive"], "/design/responsive")
    accessibility = index(d["accessibility"], "/design/accessibility")
    review = index(d["review_criteria"], "/design/review_criteria")
    rule_items = list(d["art_direction"]["anti_generic_rules"])
    for section in ("layout_rules", "typography_rules", "spacing_rules", "color_rules"):
        rule_items.extend(d[section])
    rules = index(rule_items, "/design/rules")
    for criterion in review.values():
        refs(criterion["rule_ids"], rules, criterion["id"])
    covered_rules = {rid for criterion in review.values() if criterion["required"] for rid in criterion["rule_ids"]}
    for rid in set(rules) - covered_rules:
        add("RULE_COVERAGE", rid, "No mandatory review criterion covers this design rule")
    categories = {t["category"] for t in tokens.values()}
    if not {"color", "typography", "spacing", "layout"} <= categories:
        add("TOKEN_COVERAGE", "/design/tokens", "Define color, typography, spacing and layout tokens")
    for component in components.values():
        refs(component["screen_ids"], screens, component["id"])
        refs(component["token_ids"], tokens, component["id"])
        parent = component["parent_id"]
        if parent is not None:
            refs([parent], components, component["id"])
            if parent in components and not set(component["screen_ids"]) <= set(components[parent]["screen_ids"]):
                add("COMPONENT_PARENT", component["id"], "Parent component does not belong to all child screens")
        seen, current = set(), component["id"]
        while current is not None and current in components:
            if current in seen:
                add("COMPONENT_CYCLE", component["id"], "Component tree has a parent cycle")
                break
            seen.add(current)
            current = components[current]["parent_id"]
        valid_states = set().union(*(states_by_screen.get(sid, set()) for sid in component["screen_ids"]))
        if not set(component["state_kinds"]) <= valid_states:
            add("COMPONENT_STATE", component["id"], "Component state is not used by its screens")
    for group in (responsive, accessibility):
        for item in group.values():
            refs(item["screen_ids"], screens, item["id"])
    for sid in screens:
        roots = [c for c in components.values() if sid in c["screen_ids"] and c["parent_id"] is None]
        if len(roots) != 1:
            add("COMPONENT_ROOT", sid, "Each screen must have exactly one component tree root")
        if not any(sid in c["screen_ids"] for c in components.values()):
            add("COMPONENT_COVERAGE", sid, "No component mapping for screen")
        widths = {r["viewport"]["width"] for r in responsive.values() if sid in r["screen_ids"]}
        if len(widths) < 2:
            add("RESPONSIVE_COVERAGE", sid, "Define at least two distinct viewport widths")
        if not any(sid in a["screen_ids"] for a in accessibility.values()):
            add("ACCESSIBILITY_COVERAGE", sid, "No accessibility rule for screen")
    covered = {r["category"] for r in review.values() if r["required"]}
    if covered != REVIEW_CATEGORIES:
        add("REVIEW_COVERAGE", "/design/review_criteria", "Every required review category needs a mandatory criterion")
    return findings

def _lines(value, depth=0):
    pad = "  " * depth
    lines = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}- **{key}**:")
                lines.extend(_lines(item, depth + 1))
            else:
                text = str(item).replace("\n", "\n" + pad + "  ")
                lines.append(f"{pad}- **{key}**: {text}")
    elif isinstance(value, list):
        if not value:
            lines.append(pad + "- （無）")
        for item in value:
            if isinstance(item, dict):
                lines.append(pad + "- " + item.get("id", item.get("kind", "項目")))
                lines.extend(_lines(item, depth + 1))
            else:
                lines.append(pad + "- " + str(item).replace("\n", "\n" + pad + "  "))
    return lines

def render_documents(data, stage):
    errors = _schema_errors(data, stage)
    if errors:
        raise ValueError("Cannot render structurally invalid contract")
    digest = sha(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    docs = [("UI-BRIEF.md", "UI Brief", "UI 需求簡報", "brief")]
    if stage == "design":
        docs += [("UI-SPEC.md", "UI Specification", "UI 功能與狀態規格", "spec"),
                 ("DESIGN.md", "UI Design Contract", "UI 設計契約", "design")]
    result = {}
    for filename, title, chinese, section in docs:
        m = data["metadata"]
        header = "\n".join(["---", f"document_title: {title}", f"chinese_title: {chinese}", "aka: []",
            f"established_date: {m['established_date']}", f"updated_date: {m['updated_date']}",
            f"version: {m['version']}", "---", "", "# " + chinese, "",
            "> 由 contract.json 產生。請修改契約後輸出到新目錄；本文件不是 UI 驗收證據。", "",
            f"Project: {data['project']['id']} / {data['project']['name']}", "",
            f"Contract content SHA-256: {digest}", ""])
        sections = []
        for key, value in data[section].items():
            sections.extend(["", "## " + key, ""])
            sections.extend(_lines(value) if isinstance(value, (dict, list)) else [value])
        result[filename] = header + "\n".join(sections) + "\n"
    return result

def engine_hash():
    h = hashlib.sha256()
    for path in sorted((ROOT / "ui_design_harness").glob("*.py")) + [SCHEMA]:
        h.update(path.relative_to(ROOT).as_posix().encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()

def inspect_contract(path, stage, documents=None):
    path = Path(path)
    engine_before = engine_hash()
    raw = path.read_bytes()
    data = load_json(raw.decode("utf-8-sig"))
    findings = validate_contract(data, stage)
    document_hashes = {}
    if documents is None:
        _add(findings, "DOCUMENTS_REQUIRED", "/documents", "Provide rendered documents for a gate receipt")
    elif not _schema_errors(data, stage):
        folder = Path(documents).resolve()
        for name, expected in render_documents(data, stage).items():
            doc = folder / name
            if not doc.is_file() or doc.is_symlink() or not doc.resolve().is_relative_to(folder):
                _add(findings, "DOCUMENT_MISSING", name, "Generated document missing or not an ordinary contained file")
                continue
            actual = doc.read_bytes()
            document_hashes[name] = sha(actual)
            if actual != expected.encode("utf-8"):
                _add(findings, "DOCUMENT_STALE", name, "Document differs from the current generated contract")
    if path.read_bytes() != raw or engine_hash() != engine_before:
        _add(findings, "SOURCE_CHANGED", "/", "Contract or checker changed during inspection; rerun")
    # Re-read observed files to catch a normal editor writing during inspection.
    if documents is not None:
        for name, digest in document_hashes.items():
            doc = Path(documents) / name
            if not doc.is_file() or sha(doc.read_bytes()) != digest:
                _add(findings, "SOURCE_CHANGED", name, "Document changed during inspection; rerun")
    return dict(schema_version="0.1", stage=stage, status="FAIL" if findings else "PASS",
        evidence_scope="contract_validation", ui_acceptance="UNVERIFIED",
        checked_at=datetime.now(timezone.utc).isoformat(), source_hash=sha(raw),
        engine_hash=engine_before, document_hashes=document_hashes, findings=findings,
        limitations=["Structural, traceability and generated-document freshness checks only.",
                     "No implementation, browser, visual, accessibility or usability acceptance executed.",
                     "Local hashes detect stale content; they are not signatures or a security sandbox."])

