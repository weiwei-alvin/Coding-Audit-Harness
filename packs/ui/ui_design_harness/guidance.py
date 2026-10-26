"""Scoped implementation handoff for one user story.

This module reads a freshly re-checked design contract, rejects stale receipts and
scope leaks, and emits the minimum UI context a front-end implementer needs for a
single US-NNN. It never claims implementation or UI acceptance. Suggested skills
are routed from a data registry and are only stated, never claimed as executed.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import re

from jsonschema import Draft202012Validator

from .contract import ROOT, inspect_contract, load_json, sha, unresolved

GUIDANCE_SCHEMA = ROOT / "schemas/guidance.schema.json"
RULE_SECTIONS = ("anti_generic", "layout", "typography", "spacing", "color")
LIMITATIONS = [
    "Context extraction only; no implementation, browser, visual, accessibility or usability acceptance executed.",
    "Contract gate PASS and schema-validated handoff are not UI acceptance.",
    "Local hashes detect stale content; they are not signatures or a security sandbox.",
]
# Skill routing reads its content from a data file; see docs/skill-routing-spec.md.
SKILLS_REGISTRY = ROOT / "ui_design_harness/data/skills-registry.json"
REGISTRY_PATH_ENV = "UI_DESIGN_HARNESS_SKILLS_REGISTRY"
PLATFORMS = ("web", "desktop", "mobile")  # mirrors schemas/contract.schema.json project.platform
NEEDS = ("motion", "iconography", "design_reference")
SKILL_STATUSES = ("available", "missing", "unverified")
PIN_KINDS = ("commit", "release", "unpinned")
ENTRY_FIELDS = ("id", "name", "repo", "version_pin", "pin_kind", "status", "why")
ENTRY_OPTIONAL = ("source", "pinned_at")
REGISTRY_FIELDS = ("schema_version", "kind", "platforms", "updated_date", "note")
MOTION_KEYWORDS = ("動畫", "動態", "轉場", "過渡", "淡入", "淡出", "motion", "animation", "transition", "animate")
ICON_KEYWORDS = ("圖示", "圖標", "icon", "符號")
SKILL_STATEMENT = "技能參照與狀態僅供路由：未取得、未安裝、未執行任何所列技能，亦不預告執行結果。"


def _add(findings, code, path, message):
    findings.append(dict(code=code, path=path, message=message))


def _index(items):
    return {item["id"]: item for item in items}


def _structural_ready(data):
    if not isinstance(data, dict):
        return False
    if not isinstance(data.get("spec"), dict) or not isinstance(data.get("design"), dict):
        return False
    spec_keys = ("stories", "screens", "acceptance_criteria")
    design_keys = ("art_direction", "layout_rules", "typography_rules", "spacing_rules",
        "color_rules", "tokens", "components", "review_criteria")
    try:
        art = data["design"]["art_direction"]
        return (all(k in data["spec"] for k in spec_keys)
            and all(k in data["design"] for k in design_keys)
            and isinstance(art, dict) and "anti_generic_rules" in art)
    except TypeError:
        return False


def _rules(design):
    rules = {}
    for section, items in (("anti_generic", design["art_direction"]["anti_generic_rules"]),
            ("layout", design["layout_rules"]), ("typography", design["typography_rules"]),
            ("spacing", design["spacing_rules"]), ("color", design["color_rules"])):
        for rule in items:
            rules[rule["id"]] = dict(rule, section=section)
    return rules


def _need_text(data, screens, components, tokens):
    """Closed, ordered set of contract fields scanned for need keywords.

    Deliberately excludes rule statements and review criteria: they are identical
    for every story, so scanning them would turn a need into a contract-level
    default. See docs/skill-routing-spec.md.
    """
    def text(value):
        return value if isinstance(value, str) else ""

    constraints = data["brief"].get("platform_constraints", [])
    fields = [text(value) for value in constraints] if isinstance(constraints, list) else []
    art = data["design"]["art_direction"]
    fields += [text(art.get("route")), text(art.get("intent"))]
    for screen in screens:
        fields.append(text(screen.get("purpose")))
        for state in screen.get("states", []):
            fields += [text(state.get("presentation")), text(state.get("interaction"))]
    for component in components:
        fields += [text(component.get("name")), text(component.get("behavior")),
            text(component.get("keyboard")), text(component.get("accessible_name"))]
    for token in tokens:
        fields += [text(token.get("name")), text(token.get("value")), text(token.get("rationale"))]
    return "\n".join(fields)


def derive_needs(data, screens, components, tokens):
    """Deterministic need vocabulary for one selected story; empty when nothing is derivable."""
    text = _need_text(data, screens, components, tokens).casefold()
    needs = set()
    if any(token.get("category") == "motion" for token in tokens) or any(
            keyword in text for keyword in MOTION_KEYWORDS):
        needs.add("motion")
    if any(keyword in text for keyword in ICON_KEYWORDS):
        needs.add("iconography")
    references = data["design"]["art_direction"].get("references", [])
    if isinstance(references, list) and any(isinstance(reference, dict)
            and reference.get("status") == "provided" for reference in references):
        needs.add("design_reference")
    return sorted(needs)


def _registry_path(registry_path=None):
    if registry_path is not None:
        return Path(registry_path)
    override = os.environ.get(REGISTRY_PATH_ENV)
    return Path(override) if override else SKILLS_REGISTRY


def _entry_errors(entry, path):
    if not isinstance(entry, dict):
        return [dict(code="SKILL_REGISTRY_INVALID", path=path, message="A skill entry must be an object")]
    errors = []
    for field in ENTRY_FIELDS:
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            _add(errors, "SKILL_REGISTRY_INVALID", path + "/" + field,
                f"Skill entry field {field} must be a non-empty string")
    for field in ENTRY_OPTIONAL:
        if field in entry and (not isinstance(entry[field], str) or not entry[field].strip()):
            _add(errors, "SKILL_REGISTRY_INVALID", path + "/" + field,
                f"Optional skill entry field {field} must be a non-empty string")
    unknown = sorted(set(entry) - set(ENTRY_FIELDS) - set(ENTRY_OPTIONAL))
    if unknown:
        _add(errors, "SKILL_REGISTRY_INVALID", path, f"Unknown skill entry field(s): {', '.join(unknown)}")
    if isinstance(entry.get("id"), str) and not re.fullmatch(r"SKL-[0-9]{3}", entry["id"]):
        _add(errors, "SKILL_REGISTRY_INVALID", path + "/id", "Skill id must match SKL-NNN")
    if isinstance(entry.get("repo"), str) and not re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", entry["repo"]):
        _add(errors, "SKILL_REGISTRY_INVALID", path + "/repo", "Repo must look like owner/name")
    if isinstance(entry.get("pinned_at"), str) and not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", entry["pinned_at"]):
        _add(errors, "SKILL_REGISTRY_INVALID", path + "/pinned_at", "pinned_at must be a calendar date")
    if entry.get("pin_kind") not in PIN_KINDS:
        _add(errors, "SKILL_REGISTRY_INVALID", path + "/pin_kind", f"pin_kind must be one of {', '.join(PIN_KINDS)}")
    if entry.get("status") not in SKILL_STATUSES:
        _add(errors, "SKILL_REGISTRY_INVALID", path + "/status", f"status must be one of {', '.join(SKILL_STATUSES)}")
    return errors


def _registry_errors(data):
    if not isinstance(data, dict):
        return [dict(code="SKILL_REGISTRY_INVALID", path="/", message="Skills registry must be a JSON object")]
    errors = []
    for field, expected in (("schema_version", "0.1"), ("kind", "skills_registry")):
        if data.get(field) != expected:
            _add(errors, "SKILL_REGISTRY_INVALID", "/" + field, f"Skills registry {field} must be {expected!r}")
    unknown = sorted(set(data) - set(REGISTRY_FIELDS))
    if unknown:
        _add(errors, "SKILL_REGISTRY_INVALID", "/", f"Unknown skills registry field(s): {', '.join(unknown)}")
    if "updated_date" in data and not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", data["updated_date"]):
        _add(errors, "SKILL_REGISTRY_INVALID", "/updated_date", "updated_date must be a calendar date")
    platforms = data.get("platforms")
    if not isinstance(platforms, dict):
        _add(errors, "SKILL_REGISTRY_INVALID", "/platforms", "Skills registry needs a platforms object")
        return errors
    seen = set()
    for platform, entry in platforms.items():
        if platform not in PLATFORMS:
            _add(errors, "SKILL_REGISTRY_INVALID", "/platforms/" + str(platform),
                "Platform is not a contract platform (web/desktop/mobile)")
            continue
        if not isinstance(entry, dict):
            _add(errors, "SKILL_REGISTRY_INVALID", "/platforms/" + platform, "A platform entry must be an object")
            continue
        unknown = sorted(set(entry) - {"skills", "needs"})
        if unknown:
            _add(errors, "SKILL_REGISTRY_INVALID", "/platforms/" + platform,
                f"Unknown platform field(s): {', '.join(unknown)}")
        skills, needs = entry.get("skills", []), entry.get("needs", {})
        if not isinstance(skills, list) or not isinstance(needs, dict):
            _add(errors, "SKILL_REGISTRY_INVALID", "/platforms/" + platform,
                "Platform skills must be a list and needs an object")
            continue
        for index, item in enumerate(skills):
            errors.extend(_entry_errors(item, f"/platforms/{platform}/skills/{index}"))
        for need, items in needs.items():
            if need not in NEEDS:
                _add(errors, "SKILL_REGISTRY_INVALID", f"/platforms/{platform}/needs/{need}",
                    "Need is not in the controlled vocabulary")
                continue
            if not isinstance(items, list):
                _add(errors, "SKILL_REGISTRY_INVALID", f"/platforms/{platform}/needs/{need}", "A need tier must be a list")
                continue
            for index, item in enumerate(items):
                errors.extend(_entry_errors(item, f"/platforms/{platform}/needs/{need}/{index}"))
        for item in list(skills) + [x for items in needs.values() for x in items]:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                if item["id"] in seen:
                    _add(errors, "SKILL_REGISTRY_INVALID", "/platforms", f"Duplicate skill id {item['id']}")
                seen.add(item["id"])
    return errors


def load_skills_registry(registry_path=None):
    """Return (registry, findings). registry is None when the data file cannot be used.

    The registry digest is carried alongside the data because engine_hash() covers
    only checker code and the contract schema, never data files.
    """
    path = _registry_path(registry_path)
    findings = []
    if not path.is_file():
        _add(findings, "SKILL_REGISTRY_MISSING", "/skills-registry", f"Skills registry not found at {path}")
        return None, findings
    try:
        raw = path.read_bytes()
        data = load_json(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        return None, [dict(code="SKILL_REGISTRY_INVALID", path="/skills-registry",
            message=f"Skills registry is not readable JSON: {exc}")]
    errors = _registry_errors(data)
    if errors:
        return None, errors
    return dict(data=data, hash=sha(raw)), []


def route_skills(registry, platform, needs):
    """Deterministic routing: platform tier first, then derived needs.

    Skill ids are unique across the whole registry, so no dedupe is needed here.
    """
    entry = registry["data"]["platforms"].get(platform)
    if entry is None:
        return []
    tiers = [(None, entry.get("skills", []))] + [
        (need, entry.get("needs", {}).get(need, [])) for need in sorted(needs)]
    ordered = [(need, item) for need, items in tiers for item in items]
    return [dict(id=item["id"], need=need, name=item["name"], repo=item["repo"],
        version_pin=item["version_pin"], pin_kind=item["pin_kind"], status=item["status"], why=item["why"])
        for need, item in sorted(ordered, key=lambda pair: (pair[0] or "", pair[1]["repo"], pair[1]["id"]))]


def select_guidance(data, story_id):
    """Return (selection, findings). selection is None when the slice cannot be closed."""
    findings = []
    brief, spec, design = data["brief"], data["spec"], data["design"]
    stories = _index(spec["stories"])
    story = stories.get(story_id)
    if story is None:
        _add(findings, "UNKNOWN_STORY", story_id, "No such user story in the design contract")
        return None, findings

    for question in brief["unknowns"]:
        if question["blocking"] and unresolved(question["resolution"]):
            _add(findings, "BLOCKING_UNKNOWN", question["id"],
                "Resolve the blocking discovery question before producing a handoff")
        elif not question["blocking"] and unresolved(question["resolution"]):
            if question.get("deferred_to") in ("design", "implementation"):
                _add(findings, "DEFERRED_UNKNOWN_DUE", question["id"],
                    f"{question['id']} is unresolved and deferred to {question['deferred_to']}; resolve it before implementation guidance")

    users = _index(brief["users"])
    tasks = _index(brief["tasks"])
    flows = _index(brief["flows"])
    successes = _index(brief["success_criteria"])
    screens = _index(spec["screens"])
    acs = _index(spec["acceptance_criteria"])

    selected_screens = [screens[sid] for sid in story["screen_ids"] if sid in screens]
    owned_acs = {aid: ac for aid, ac in acs.items() if ac["story_id"] == story["id"]}
    if not selected_screens or not owned_acs:
        _add(findings, "EMPTY_SELECTION", story["id"],
            "Selected story resolves to no screens or no owned UI-AC; an empty handoff is not accepted")

    for screen in selected_screens:
        kinds = [state["kind"] for state in screen["states"]]
        for state in screen["states"]:
            kind, variant = state["kind"], state.get("variant")
            if not any(ac["screen_id"] == screen["id"] and ac["state"] == kind
                    and ac.get("variant") == variant and ac["required"] for ac in owned_acs.values()):
                _add(findings, "MISSING_STATE_AC", screen["id"] + "/" + kind + (":" + variant if variant else ""),
                    "Selected story has no required UI-AC for this state variant")

    selected_ids = {screen["id"] for screen in selected_screens}
    components = _index(design["components"])
    included_components = {cid: c for cid, c in components.items()
        if not c.get("shared") and set(c["screen_ids"]) <= selected_ids}
    shared = [c for c in components.values() if c.get("shared") and set(c["screen_ids"]) & selected_ids]
    for cid, component in included_components.items():
        parent = component["parent_id"]
        if parent is not None and parent not in included_components:
            outside = sorted(set(components[parent]["screen_ids"]) - selected_ids) if parent in components else []
            owners = sorted(st["id"] for st in stories.values() if set(st["screen_ids"]) & set(outside))
            _add(findings, "SCOPE_GAP", cid,
                f"Parent {parent} spans screens {outside}, owned by {owners}; split root per screen or use a shared component")
            findings[-1]["cause"] = dict(component_id=parent, extra_screen_ids=outside, story_ids=owners,
                action="Split root per screen or declare an independent shared component")
    for sid in selected_ids:
        roots = [c for c in included_components.values() if sid in c["screen_ids"] and c["parent_id"] is None]
        if len(roots) != 1:
            _add(findings, "SCOPE_GAP", sid, "Selected screen has no single component root inside the story scope")

    tokens = _index(design["tokens"])
    token_ids = sorted({tid for c in list(included_components.values()) + shared for tid in c["token_ids"]})
    for tid in token_ids:
        if tid not in tokens:
            _add(findings, "SCOPE_GAP", tid, "Component references a token missing from the contract")

    rules = _rules(design)
    review = _index(design["review_criteria"])
    required_criteria = [c for c in review.values() if c["required"]]
    rule_usage = {}
    for criterion in required_criteria:
        for rid in criterion["rule_ids"]:
            if rid not in rules:
                _add(findings, "MISSING_RULE", criterion["id"], f"Required criterion references unknown rule {rid}")
                continue
            rule_usage.setdefault(rid, []).append(criterion["id"])

    if findings:
        return None, findings

    screens_out = []
    for screen in selected_screens:
        screen_acs = sorted((ac for ac in owned_acs.values() if ac["screen_id"] == screen["id"]),
            key=lambda a: a["id"])
        screens_out.append(dict(screen, acceptance_criteria=screen_acs))

    rules_out = []
    for rid in sorted(rule_usage):
        rule = rules[rid]
        from .contract import TOKEN_REF
        def resolve(text):
            return TOKEN_REF.sub(lambda match: tokens[match.group()[1:]]["value"], text)
        rules_out.append(dict(id=rule["id"], statement=rule["statement"], verification=rule["verification"],
            resolved_statement=resolve(rule["statement"]), resolved_verification=resolve(rule["verification"]),
            token_ids=rule.get("token_ids", []),
            section=rule["section"], criterion_ids=sorted(rule_usage[rid])))

    methods = {"automated": 0, "manual": 0, "hybrid": 0}
    for ac in owned_acs.values():
        methods[ac["method"]] += 1

    selected_tokens = [tokens[tid] for tid in token_ids]
    selected_components = sorted(included_components.values(), key=lambda c: c["id"])
    shared_refs = [dict(id=c["id"], name=c["name"], screen_ids=sorted(set(c["screen_ids"]) & selected_ids),
        token_ids=c["token_ids"], read_only=True) for c in sorted(shared, key=lambda c: c["id"])]
    selection = dict(
        story=story,
        user=users[story["user_id"]],
        task=tasks[story["task_id"]],
        flow=flows[tasks[story["task_id"]]["flow_id"]],
        success_criteria=[successes[sid] for sid in story["success_criteria_ids"]],
        screens=screens_out,
        components=selected_components,
        shared_components=shared_refs,
        tokens=selected_tokens,
        rules=rules_out,
        review_criteria=sorted(required_criteria, key=lambda c: c["id"]),
        acceptance_methods=methods,
        acceptance_count=len(owned_acs),
        needs=derive_needs(data, selected_screens, selected_components, selected_tokens),
    )
    return selection, findings


def _payload(data, fresh, receipt_bytes, story_id, selection, registry):
    project = data["project"]
    suggested = route_skills(registry, project["platform"], selection["needs"])
    return dict(
        schema_version="0.1",
        kind="implementation_guidance",
        status="PASS",
        story_id=story_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        ui_acceptance="UNVERIFIED",
        source=dict(stage="design", source_hash=fresh["source_hash"], engine_hash=fresh["engine_hash"],
            receipt_hash=sha(receipt_bytes), document_hashes=fresh["document_hashes"]),
        story=selection["story"],
        user=selection["user"],
        task=selection["task"],
        flow=selection["flow"],
        success_criteria=selection["success_criteria"],
        screens=selection["screens"],
        components=selection["components"],
        shared_components=selection["shared_components"],
        tokens=selection["tokens"],
        rules=selection["rules"],
        review_criteria=selection["review_criteria"],
        suggested_skills=dict(platform=project["platform"], needs=selection["needs"],
            registry_hash=registry["hash"], statement=SKILL_STATEMENT, skills=suggested),
        verification=dict(
            reproduce=[
                "python -m ui_design_harness check --contract <contract> --stage design --documents <documents> --receipt <fresh-receipt>",
                f"python -m ui_design_harness guidance --contract <contract> --documents <documents> --receipt <fresh-receipt> --story {story_id}",
            ],
            acceptance_methods=selection["acceptance_methods"],
            before_implementation=[
                "Confirm the design gate still passes and the receipt is fresh for this contract and documents.",
                f"Build the {selection['acceptance_count']} listed required UI-AC states for story {story_id} and prepare their evidence artifacts.",
                "Apply only the listed RULE-NNN design rules; do not invent scope outside the selected screens.",
                f"Treat the {len(suggested)} suggested skills for story {story_id} as references with the stated status; none has been fetched, installed or executed.",
            ],
        ),
        not_included=[
            "Screens, components and UI-AC owned by user stories other than the selected one.",
            "Review criteria that are not required for acceptance.",
            "Any implementation, browser, visual, accessibility or usability evidence; those belong to later milestones.",
            "Fetching, installing or executing any suggested skill; suggested_skills states references and status only.",
        ],
        limitations=list(LIMITATIONS),
    )


def build_guidance(contract_path, documents, receipt_path, story_id, registry_path=None):
    """Re-check the design gate, bind a fresh receipt, and return a scoped handoff report."""
    contract_path = Path(contract_path)
    receipt_bytes = Path(receipt_path).read_bytes()
    data = load_json(contract_path.read_text(encoding="utf-8-sig"))
    fresh = inspect_contract(contract_path, "design", documents)

    findings = []
    if fresh["status"] != "PASS":
        _add(findings, "CONTRACT_GATE_FAIL", "/",
            "The design gate did not pass for the current contract and documents")

    try:
        receipt = load_json(receipt_bytes.decode("utf-8-sig"))
    except ValueError:
        receipt = None
        _add(findings, "RECEIPT_INVALID", "/receipt", "Receipt is not valid JSON")
    if receipt is not None:
        if not isinstance(receipt, dict) or "source_hash" not in receipt or "engine_hash" not in receipt:
            _add(findings, "RECEIPT_INVALID", "/receipt", "Receipt is missing required hash fields")
        else:
            for field in ("stage", "status", "source_hash", "engine_hash", "document_hashes"):
                if receipt.get(field) != fresh.get(field):
                    _add(findings, "STALE_RECEIPT", field,
                        "Receipt does not match the freshly checked contract, engine or documents")

    selection = None
    if _structural_ready(data):
        selection, selection_findings = select_guidance(data, story_id)
        findings.extend(selection_findings)

    # The registry is loaded only once the rest of the handoff is producible, so a
    # rejection never mixes unrelated causes.
    registry = None
    if not findings and selection is not None:
        registry, registry_findings = load_skills_registry(registry_path)
        findings.extend(registry_findings)

    report = dict(schema_version="0.1", kind="implementation_guidance", story_id=story_id,
        ui_acceptance="UNVERIFIED", checked_at=datetime.now(timezone.utc).isoformat(),
        findings=findings, limitations=list(LIMITATIONS))

    if findings or selection is None or registry is None:
        report["status"] = "FAIL"
        return report

    payload = _payload(data, fresh, receipt_bytes, story_id, selection, registry)
    validator = Draft202012Validator(load_json(GUIDANCE_SCHEMA.read_text(encoding="utf-8")))
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        raise ValueError("Internal guidance payload failed schema validation: " + errors[0].message)
    report["status"] = "PASS"
    report["guidance"] = payload
    return report
