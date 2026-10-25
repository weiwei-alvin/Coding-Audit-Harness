"""Project-relative planning gate receipt freshness checks.

The kernel does not interpret UI contracts. It verifies that a declared PASS
receipt still matches the source, checker implementation and rendered documents.
Local hashes are not signatures or an authentication boundary.
"""
import hashlib
import json
from pathlib import Path
import re

SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _contained(root, path):
    if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
        raise ValueError(f"Gate evidence path must be project-relative: {path!r}")
    candidate = root / path
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()) or candidate.is_symlink():
        raise ValueError(f"Gate evidence escapes the project: {path!r}")
    return candidate


def _hex_digest(value):
    return isinstance(value, str) and bool(SHA256.fullmatch(value))


def verify_gate_receipt(project_root, config):
    """Return validation errors for one planning-stage receipt declaration."""
    root = Path(project_root).resolve()
    errors = []
    try:
        receipt_path = _contained(root, config["path"])
        source = _contained(root, config["source"])
        documents = _contained(root, config["documents"])
        engine_root = _contained(root, config["engine_root"])
        if not receipt_path.is_file() or not source.is_file() or not documents.is_dir() or not engine_root.is_dir():
            return ["Gate evidence requires existing receipt, source, documents and engine files"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        if not isinstance(receipt, dict):
            return ["Gate receipt is not a JSON object"]
        if receipt.get("status") != "PASS" or receipt.get("stage") != config["stage"]:
            errors.append("Gate receipt is not a PASS for the declared stage")
        if receipt.get("evidence_scope") != "contract_validation":
            errors.append("Gate receipt has an unexpected evidence scope")
        if not _hex_digest(receipt.get("source_hash")) or receipt["source_hash"] != hashlib.sha256(source.read_bytes()).hexdigest():
            errors.append("Gate receipt source_hash is missing or stale")
        h = hashlib.sha256()
        count = 0
        for pattern in config["engine_patterns"]:
            if pattern.startswith("/") or ".." in Path(pattern).parts:
                raise ValueError("Gate engine pattern must be relative and confined")
            paths = sorted(engine_root.glob(pattern))
            if not paths:
                errors.append(f"Gate engine pattern matched no files: {pattern}")
            for path in paths:
                if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(engine_root.resolve()):
                    raise ValueError("Gate engine source is not a contained ordinary file")
                h.update(path.relative_to(engine_root).as_posix().encode())
                h.update(b"\0")
                h.update(path.read_bytes())
                h.update(b"\0")
                count += 1
        if not count or not _hex_digest(receipt.get("engine_hash")) or receipt["engine_hash"] != h.hexdigest():
            errors.append("Gate receipt engine_hash is missing or stale")
        hashes = receipt.get("document_hashes")
        if not isinstance(hashes, dict) or not hashes:
            errors.append("Gate receipt contains no document hashes")
        else:
            for name, expected in hashes.items():
                path = _contained(documents, name)
                if not _hex_digest(expected) or not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    errors.append(f"Gate receipt document missing or stale: {name}")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"Gate evidence unreadable or invalid: {exc}")
    return errors
