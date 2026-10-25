"""Pipeline definition as data (T-006 contract phase).

A definition file states which stages exist, their order, kind, gate verdicts,
hooks and evidence-tier requirements. The engine derives runtime stage data from
it; the historical PipelineStage enum remains only as an import alias. Resolution
order is explicit: an explicit path, then the project's own .harness/pipeline.json.
The bundled harness/pipeline.default.json is a file operators copy, never a silent
fallback for init (init passes allow_bundled=False). It is used at runtime only for
legacy states that predate the recorded definition, so old projects stay readable.
"""
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

HARNESS_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SCHEMA_PATH = HARNESS_ROOT / "pipeline.schema.json"
BUNDLED_DEFAULT_PATH = HARNESS_ROOT / "pipeline.default.json"
PROJECT_PIPELINE_RELATIVE = Path(".harness") / "pipeline.json"

STAGE_STATUSES = ("IN_PROGRESS", "READY_FOR_GATE")
KNOWN_HOOKS = ("validate_ticket_dependencies", "start_first_ticket")
GATE_HOOKS = ("validate_ticket_dependencies", "require_conditional_gates")
# Kernel-evaluated activation conditions for conditional stages. Keys are
# domain-neutral: a value is active when the project's own declared data
# matches it. Unknown keys stay display-only unless a gate hook evaluates them.
CONDITION_KEYS = ("golden_path_declares_collector",)


class PipelineDefinitionError(ValueError):
    """Raised when a pipeline definition is missing, unreadable or invalid."""


class PipelineDefinition:
    """Validated view over one pipeline definition file."""

    def __init__(self, data, source_path, raw_bytes):
        self.data = data
        self.source = str(Path(source_path).resolve())
        self.raw_bytes = raw_bytes
        self.stages = data["stages"]
        self.ids = [stage["id"] for stage in self.stages]
        self.by_id = {stage["id"]: stage for stage in self.stages}

    @property
    def name(self):
        return self.data["pipeline"]

    @property
    def first_stage(self):
        return self.ids[0]

    @property
    def terminal_stage(self):
        for stage in self.stages:
            if stage.get("terminal"):
                return stage["id"]
        return self.ids[-1]

    @property
    def work_stage(self):
        """First execution stage; ticket work starts here in the default pipeline."""
        for stage in self.stages:
            if stage["kind"] == "execution":
                return stage["id"]
        raise PipelineDefinitionError("Pipeline definition has no execution stage")

    @property
    def approval_stage(self):
        """Planning stage whose PASS approves the plan, if the definition declares one."""
        for stage in self.stages:
            if "validate_ticket_dependencies" in self.gate_hooks(stage["id"]):
                return stage["id"]
        return None

    def digest(self):
        return hashlib.sha256(self.raw_bytes).hexdigest()

    def kind(self, stage_id):
        return self._stage(stage_id)["kind"]

    def is_planning(self, stage_id):
        return self.kind(stage_id) == "planning"

    def is_execution(self, stage_id):
        return self.kind(stage_id) == "execution"

    def gate_verdicts(self, stage_id):
        stage = self._stage(stage_id)
        if stage["kind"] != "planning":
            raise PipelineDefinitionError(f"Stage {stage_id} is not a gated planning stage")
        return list(stage["gate_verdicts"])

    def next_stage(self, stage_id):
        return self._stage(stage_id).get("next")

    def hook(self, stage_id, name):
        return self._stage(stage_id).get(name)

    def gate_receipt(self, stage_id):
        """Optional project-relative, content-bound planning gate evidence."""
        return self._stage(stage_id).get("gate_receipt")

    def gate_hooks(self, stage_id):
        """Gate hooks declared for a planning stage; a string stays accepted."""
        value = self._stage(stage_id).get("on_gate_pass")
        if value is None:
            return []
        return [value] if isinstance(value, str) else list(value)

    def conditional_stage_errors(self):
        """Strictness for definitions that ask the kernel to enforce conditions.

        Without this hook a conditional stage is a display marker only. With it,
        every condition must be one the kernel can actually evaluate, so an
        unenforceable stage can never claim enforcement.
        """
        errors = []
        if any("require_conditional_gates" in self.gate_hooks(s["id"]) for s in self.stages):
            for stage in self.stages:
                if stage.get("conditional") and stage.get("condition") not in CONDITION_KEYS:
                    errors.append(
                        f"Stage {stage['id']} uses condition {stage.get('condition')!r} "
                        f"but a require_conditional_gates hook is declared; "
                        f"supported conditions: {', '.join(CONDITION_KEYS)}")
        return errors

    def is_conditional(self, stage_id):
        return bool(self._stage(stage_id).get("conditional"))

    def required_evidence_tiers(self, stage_id):
        """Tiers a review at this stage must supply (T-008); empty means unconstrained."""
        return list(self._stage(stage_id).get("required_evidence_tiers", []))

    def sequence_display(self):
        """Human-readable stage sequence; conditional stages carry a marker."""
        parts = []
        for stage in self.stages:
            marker = "*" if stage.get("conditional") else ""
            parts.append(stage["id"] + marker)
        return " -> ".join(parts)

    def planning_transitions(self):
        """Derived (stage, stage_status) -> allowed next, matching the engine table shape."""
        table = {}
        for stage in self.stages:
            if stage["kind"] != "planning":
                continue
            stage_id = stage["id"]
            table[(stage_id, "IN_PROGRESS")] = ["READY_FOR_GATE"]
            table[(stage_id, "READY_FOR_GATE")] = [stage["next"]]
        return table

    def _stage(self, stage_id):
        if stage_id not in self.by_id:
            raise PipelineDefinitionError(f"Unknown pipeline stage: {stage_id}")
        return self.by_id[stage_id]


def _semantic_errors(data):
    errors = []
    stages = data["stages"]
    ids = [stage["id"] for stage in stages]
    for stage_id in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"Duplicate stage id: {stage_id}")
    for stage in stages:
        nxt = stage.get("next")
        if nxt is not None and nxt not in ids:
            errors.append(f"Stage {stage['id']} next references unknown stage {nxt}")
        if nxt == stage["id"]:
            errors.append(f"Stage {stage['id']} cannot be its own next stage")
        for hook_name in ("on_gate_pass", "on_enter"):
            hook = stage.get(hook_name)
            if hook is None:
                continue
            if hook_name == "on_gate_pass":
                hooks = [hook] if isinstance(hook, str) else hook
                if isinstance(hooks, list):
                    for name in hooks:
                        if name not in GATE_HOOKS:
                            errors.append(f"Stage {stage['id']} uses unknown gate hook on_gate_pass={name}")
                    if len(hooks) != len(set(hooks)):
                        errors.append(f"Stage {stage['id']} declares duplicate gate hooks")
            elif hook not in KNOWN_HOOKS:
                errors.append(f"Stage {stage['id']} uses unknown hook {hook_name}={hook}")
        if stage.get("required_evidence_tiers") and stage["kind"] != "execution":
            errors.append(f"Stage {stage['id']} must be an execution stage to require evidence tiers")
        if stage.get("entry") and stage["kind"] != "planning":
            errors.append(f"Entry stage {stage['id']} must be a planning stage")
    terminals = [stage["id"] for stage in stages if stage.get("terminal")]
    if len(terminals) > 1:
        errors.append(f"Only one terminal stage allowed: {terminals}")
    if terminals and terminals[0] != ids[-1]:
        errors.append(f"Terminal stage {terminals[0]} must be the last stage")
    if any(stage.get("next") is None for stage in stages if not stage.get("terminal")):
        errors.append("A non-terminal stage must declare next")
    return errors


def load_definition(path):
    """Read and fully validate one definition file; raise PipelineDefinitionError."""
    path = Path(path)
    if not path.is_file():
        raise PipelineDefinitionError(f"Pipeline definition not found: {path}")
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except ValueError as exc:
        raise PipelineDefinitionError(f"Pipeline definition is not valid JSON: {path}: {exc}") from exc
    schema = json.loads(PIPELINE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(data),
        key=lambda e: str(list(e.absolute_path)))
    if errors:
        raise PipelineDefinitionError(
            f"Pipeline definition failed schema validation: {path}: {errors[0].message}")
    semantic = _semantic_errors(data)
    if semantic:
        raise PipelineDefinitionError(
            f"Pipeline definition is inconsistent: {path}: {'; '.join(semantic)}")
    definition = PipelineDefinition(data, path, raw)
    strict = definition.conditional_stage_errors()
    if strict:
        raise PipelineDefinitionError(
            f"Pipeline definition is inconsistent: {path}: {'; '.join(strict)}")
    return definition


def resolve_definition(project_root, explicit_path=None, allow_bundled=True):
    """Resolve a definition: explicit path, then the project file, then (optionally) bundled.

    Raises PipelineDefinitionError naming what was tried when nothing resolves.
    """
    project_root = Path(project_root)
    candidates = []
    if explicit_path is not None:
        candidates.append(Path(explicit_path))
    candidates.append(project_root / PROJECT_PIPELINE_RELATIVE)
    if allow_bundled:
        candidates.append(BUNDLED_DEFAULT_PATH)
    problems = []
    for candidate in candidates:
        try:
            return load_definition(candidate)
        except PipelineDefinitionError as exc:
            problems.append(str(exc))
    tried = ", ".join(str(c) for c in candidates)
    raise PipelineDefinitionError(
        f"No usable pipeline definition (tried {tried}); copy {BUNDLED_DEFAULT_PATH} "
        f"to {PROJECT_PIPELINE_RELATIVE} or pass an explicit path. Details: {' | '.join(problems)}")


def definition_for_state(project_root, state):
    """Definition that governs one runtime state.

    A state written by init records the definition it adopted; that file is
    authoritative while it exists. Legacy states (written before T-006) have no
    record: resolve the project file, then the bundled default, so they remain
    readable without silently changing a newer project's pipeline.
    """
    project_root = Path(project_root)
    recorded = ((state or {}).get("pipeline_definition") or {}).get("source")
    if recorded:
        candidates = [Path(recorded)]
        if not Path(recorded).is_absolute():
            candidates.append(project_root / recorded)
        problems = []
        for candidate in candidates:
            try:
                return load_definition(candidate)
            except PipelineDefinitionError as exc:
                problems.append(str(exc))
        raise PipelineDefinitionError(
            f"Recorded pipeline definition is not readable: {recorded}. "
            f"Restore it or re-init the project. Details: {' | '.join(problems)}")
    return resolve_definition(project_root, allow_bundled=True)
