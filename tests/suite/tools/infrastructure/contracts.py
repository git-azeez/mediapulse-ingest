from __future__ import annotations

import json
import urllib.parse
from typing import Any, Iterable

from ..reporting.errors import SubmissionFailure
from .terraform import decode_json_value, statements


def exact_string_set(actual: Iterable[Any], expected: Iterable[Any], label: str) -> set[str]:
    actual_set = {str(value) for value in actual if value not in (None, "")}
    expected_set = {str(value) for value in expected if value not in (None, "")}
    if actual_set != expected_set:
        raise SubmissionFailure(
            f"{label} are {sorted(actual_set)}, expected exactly {sorted(expected_set)}"
        )
    return actual_set


def _required_int(value: Any, expected: int, label: str) -> None:
    try:
        actual = int(value)
    except (TypeError, ValueError) as exc:
        raise SubmissionFailure(f"{label} is absent or non-numeric") from exc
    if actual != expected:
        raise SubmissionFailure(f"{label} is {actual}, expected exactly {expected}")


def validate_sqs_contract(
    main: dict[str, Any],
    dlq: dict[str, Any],
    expected_dlq_arn: str,
) -> dict[str, Any]:
    """Validate canonical queue attributes from either state or live APIs."""
    _required_int(main.get("visibility_timeout"), 2, "main queue visibility timeout")
    _required_int(main.get("receive_wait_time"), 1, "main queue receive wait time")
    _required_int(main.get("retention"), 345600, "main queue retention")
    _required_int(dlq.get("retention"), 1209600, "DLQ retention")
    if str(main.get("fifo", "false")).lower() in {"true", "1"}:
        raise SubmissionFailure("the main event queue must be standard, not FIFO")
    if str(dlq.get("fifo", "false")).lower() in {"true", "1"}:
        raise SubmissionFailure("the dead-letter queue must be standard, not FIFO")

    redrive = decode_json_value(main.get("redrive_policy"))
    if not isinstance(redrive, dict):
        raise SubmissionFailure("main queue RedrivePolicy is absent or invalid JSON")
    if str(redrive.get("deadLetterTargetArn")) != str(expected_dlq_arn):
        raise SubmissionFailure("main queue redrives to a different DLQ")
    _required_int(redrive.get("maxReceiveCount"), 3, "redrive maxReceiveCount")
    return redrive


def validate_esm_contract(
    mapping: dict[str, Any],
    *,
    allow_missing_window: bool = False,
) -> None:
    _required_int(mapping.get("batch_size"), 10, "event source mapping batch size")
    if not (allow_missing_window and mapping.get("batching_window") is None):
        _required_int(mapping.get("batching_window"), 0, "event source mapping batching window")
    exact_string_set(
        mapping.get("response_types") or (),
        ("ReportBatchItemFailures",),
        "event source mapping response types",
    )
    enabled = mapping.get("enabled")
    if isinstance(enabled, str):
        enabled = enabled.lower() in {"true", "enabled", "enabling"}
    if enabled is not True:
        raise SubmissionFailure("the projector event source mapping is disabled")


def _schema_pairs(items: Any, *, state: bool) -> set[tuple[str, str]]:
    if not isinstance(items, list):
        return set()
    name_key = "attribute_name" if state else "AttributeName"
    type_key = "key_type" if state else "KeyType"
    return {
        (str(item.get(name_key)), str(item.get(type_key)).upper())
        for item in items
        if isinstance(item, dict) and item.get(name_key) and item.get(type_key)
    }


def validate_dynamodb_contract(table: dict[str, Any], *, state: bool) -> None:
    if state:
        if table.get("hash_key") != "PK" or table.get("range_key") != "SK":
            raise SubmissionFailure("projection table primary key must be PK/SK")
        attributes = {
            (str(item.get("name")), str(item.get("type")).upper())
            for item in table.get("attribute", []) or []
            if isinstance(item, dict)
        }
        indexes = table.get("global_secondary_index", []) or []
        gsi = next(
            (item for item in indexes if isinstance(item, dict) and item.get("name") == "GSI1"),
            None,
        )
        if not gsi:
            raise SubmissionFailure("projection table is missing GSI1")
        schema = _schema_pairs(gsi.get("key_schema"), state=True)
        # Older provider state exposes hash_key/range_key but not key_schema.
        if not schema:
            schema = {
                (str(gsi.get("hash_key")), "HASH"),
                (str(gsi.get("range_key")), "RANGE"),
            }
        projection = str(gsi.get("projection_type", "")).upper()
    else:
        schema = _schema_pairs(table.get("KeySchema"), state=False)
        if schema != {("PK", "HASH"), ("SK", "RANGE")}:
            raise SubmissionFailure("live projection table primary key must be PK/SK")
        attributes = {
            (str(item.get("AttributeName")), str(item.get("AttributeType")).upper())
            for item in table.get("AttributeDefinitions", []) or []
            if isinstance(item, dict)
        }
        indexes = table.get("GlobalSecondaryIndexes", []) or []
        gsi = next(
            (item for item in indexes if isinstance(item, dict) and item.get("IndexName") == "GSI1"),
            None,
        )
        if not gsi:
            raise SubmissionFailure("live projection table is missing GSI1")
        schema = _schema_pairs(gsi.get("KeySchema"), state=False)
        projection = str((gsi.get("Projection") or {}).get("ProjectionType", "")).upper()

    required_attributes = {
        ("PK", "S"),
        ("SK", "S"),
        ("GSI1PK", "S"),
        ("GSI1SK", "S"),
    }
    if not required_attributes.issubset(attributes):
        raise SubmissionFailure("projection table PK/SK/GSI1 key attributes must all be strings")
    if schema != {("GSI1PK", "HASH"), ("GSI1SK", "RANGE")}:
        raise SubmissionFailure("GSI1 key schema must be GSI1PK/GSI1SK")
    if projection != "ALL":
        raise SubmissionFailure("GSI1 projection type must be ALL")


def trust_services(document: Any) -> set[str]:
    if isinstance(document, str):
        document = urllib.parse.unquote(document)
    document = decode_json_value(document)
    if not isinstance(document, dict):
        return set()
    services: set[str] = set()
    for statement in statements(document):
        if str(statement.get("Effect", "Allow")).lower() != "allow":
            continue
        actions = statement.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        if "sts:assumerole" not in {str(action).lower() for action in actions}:
            continue
        principal = statement.get("Principal", {})
        if not isinstance(principal, dict):
            continue
        values = principal.get("Service", [])
        if isinstance(values, str):
            values = [values]
        services.update(str(value) for value in values)
    return services


def validate_trust(document: Any, expected_service: str, label: str) -> None:
    exact_string_set(trust_services(document), (expected_service,), f"{label} trust principals")


def validate_database_url(value: Any, database: dict[str, Any], label: str) -> None:
    try:
        parsed = urllib.parse.urlparse(str(value))
        port = parsed.port
    except ValueError as exc:
        raise SubmissionFailure(f"{label} DATABASE_URL is invalid") from exc
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or parsed.hostname != str(database.get("proxy_host"))
        or port != int(database.get("port") or 0)
        or parsed.path != f"/{database.get('name')}"
        or not parsed.username
        or parsed.password in (None, "")
    ):
        raise SubmissionFailure(f"{label} DATABASE_URL does not match the manifest RDS endpoint")


def validate_cache_endpoint(value: Any, cache: dict[str, Any], label: str) -> None:
    raw = str(value or "")
    parsed = urllib.parse.urlparse(raw if "://" in raw else f"redis://{raw}")
    try:
        port = parsed.port
    except ValueError as exc:
        raise SubmissionFailure(f"{label} VALKEY_ENDPOINT is invalid") from exc
    allowed_hosts = {
        str(cache.get("proxy_host") or ""),
        str(cache.get("address") or ""),
    } - {""}
    if parsed.scheme != "redis" or parsed.hostname not in allowed_hosts or port != int(cache.get("port") or 0):
        raise SubmissionFailure(f"{label} VALKEY_ENDPOINT does not match the manifest cache endpoint")


def environment_map(container: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in container.get("environment", []) or []:
        if isinstance(item, dict) and item.get("name") is not None:
            values[str(item["name"])] = str(item.get("value", ""))
    return values


def validate_common_gcp_environment(
    environment: dict[str, Any], manifest: dict[str, Any], label: str
) -> None:
    expected = {
        "GOOGLE_CLOUD_PROJECT": str(manifest.get("project_id")),
        "GCP_ENDPOINT_URL": str(manifest.get("gcp_endpoint_url")),
    }
    for key, value in expected.items():
        if str(environment.get(key, "")) != value:
            raise SubmissionFailure(f"{label} {key} does not match the manifest")


def redacted(value: Any) -> str:
    """Stable detail helper that never emits credential-bearing URLs."""
    if not isinstance(value, str):
        return json.dumps(value, sort_keys=True, default=str)
    parsed = urllib.parse.urlparse(value)
    if parsed.password is None:
        return value
    host = parsed.hostname or ""
    if parsed.port:
        host += f":{parsed.port}"
    return urllib.parse.urlunparse(
        (parsed.scheme, f"{parsed.username}:<redacted>@{host}", parsed.path, "", parsed.query, "")
    )
