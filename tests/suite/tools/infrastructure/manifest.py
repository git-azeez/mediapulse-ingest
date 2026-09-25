from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..reporting.errors import SubmissionFailure


ROLES = ("api", "processor", "relay", "archiver")


def manifest_schema_path(_tests_dir: Path) -> Path:
    for candidate_str in (
        "/opt/cinderroute-verifier/contracts/manifest.schema.json",
        str(_tests_dir.parent / "runtime" / "manifest.schema.json"),
    ):
        candidate = Path(candidate_str)
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError("the verifier image is missing the public manifest.schema.json contract")


def _safe_error(error: Any) -> str:
    path = ".".join(str(part) for part in error.absolute_path) or "$"
    keyword = str(error.validator or "schema")
    # Do not render `error.instance`: auth client secrets are part of the
    # manifest and must never be echoed into a score summary.
    if keyword == "required":
        missing = sorted(set(error.validator_value or ()) - set(error.instance or {}))
        return f"{path}: missing required field(s) {missing}"
    if keyword == "additionalProperties":
        allowed = set((error.schema or {}).get("properties", {}))
        extras = sorted(set(error.instance or {}) - allowed) if isinstance(error.instance, dict) else []
        return f"{path}: unexpected field(s) {extras}"
    if keyword == "type":
        return f"{path}: expected type {error.validator_value}"
    if keyword == "format":
        return f"{path}: expected format {error.validator_value}"
    if keyword in {"const", "pattern", "minimum", "maximum", "minLength", "minItems", "uniqueItems"}:
        return f"{path}: failed {keyword}={error.validator_value!r}"
    return f"{path}: failed schema keyword {keyword}"


def validate_manifest_contract(
    manifest: dict[str, Any],
    task_config: dict[str, Any],
    tests_dir: Path,
) -> None:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:  # pragma: no cover - verifier image invariant
        raise RuntimeError("verifier image is missing its pinned jsonschema dependency") from exc

    path = manifest_schema_path(tests_dir)
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - build invariant
        raise RuntimeError(f"could not load public manifest schema: {path}") from exc

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(manifest), key=lambda item: tuple(str(part) for part in item.absolute_path))
    if errors:
        summaries = [_safe_error(error) for error in errors[:8]]
        suffix = f" (+{len(errors) - 8} more)" if len(errors) > 8 else ""
        raise SubmissionFailure(f"manifest violates the public JSON Schema: {'; '.join(summaries)}{suffix}")

    mismatches: list[str] = []
    for role in ROLES:
        entry = manifest["approved_images"].get(role, {})
        expected_ref = task_config.get(f"{role}_image") or task_config.get("projector_image")
        expected_id = task_config.get(f"{role}_image_id") or task_config.get("projector_image_id")
        if isinstance(entry, str):
            actual_ref = entry
            actual_id = None
        elif isinstance(entry, dict):
            actual_ref = (
                entry.get("reference")
                or entry.get("image")
                or entry.get("uri")
                or (expected_ref if expected_ref in entry.values() else next((v for v in entry.values() if isinstance(v, str)), None))
            )
            actual_id = entry.get("image_id") or entry.get("digest")
        else:
            actual_ref = None
            actual_id = None
        if actual_ref != expected_ref:
            mismatches.append(f"approved_images.{role}.reference")
        if expected_id and actual_id and actual_id != expected_id:
            mismatches.append(f"approved_images.{role}.image_id")
    for manifest_key, runtime_key in (
        ("prefix", "resource_prefix"),
        ("project_id", "gcp_project_id"),
        ("region", "region"),
        ("gcp_endpoint_url", "gcp_endpoint_url"),
    ):
        if manifest.get(manifest_key) != task_config.get(runtime_key):
            mismatches.append(manifest_key)
    if mismatches:
        raise SubmissionFailure(
            "manifest discovery hints do not match the task configuration: " + ", ".join(mismatches)
        )
