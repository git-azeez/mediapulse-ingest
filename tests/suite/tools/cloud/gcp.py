from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

from ..execution.process import run
from ..reporting.errors import CommandFailure, HarnessError


class GcpCli:
    def __init__(self, endpoint: str, region: str, evidence_dir: Path | None = None, project_id: str = ""):
        self.endpoint = (endpoint or "http://gcp:4588").rstrip("/")
        self.region = region or "us-central1"
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID", "mediapulse")
        self.evidence_dir = evidence_dir
        self._counter = 0
        self.env = {
            "GOOGLE_CLOUD_PROJECT": self.project_id,
            "GCP_ENDPOINT_URL": self.endpoint,
            "CLOUDSDK_CORE_PROJECT": self.project_id,
        }

    def gcp_get(self, path: str, timeout: float = 10.0) -> dict[str, Any]:
        import urllib.error
        import urllib.request

        url = f"{self.endpoint}/{path.lstrip('/')}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                if not raw.strip():
                    return {}
                data = json.loads(raw)
                return data if isinstance(data, dict) else {"items": data}
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}
            return {"_http_status": exc.code}
        except Exception as exc:
            return {"_error": str(exc)}

    @staticmethod
    def _encode_args(options: dict[str, Any] | None) -> list[str]:
        encoded: list[str] = []
        for key, value in (options or {}).items():
            flag = "--" + key.replace("_", "-")
            if value is True:
                encoded.append(flag)
            elif value is False:
                encoded.append("--no-" + key.replace("_", "-"))
            elif value is None:
                continue
            elif isinstance(value, (dict, list)):
                encoded.extend([flag, json.dumps(value, separators=(",", ":"))])
            elif isinstance(value, tuple):
                encoded.append(flag)
                encoded.extend(str(item) for item in value)
            else:
                encoded.extend([flag, str(value)])
        return encoded

    def call(
        self,
        service: str,
        operation: str,
        options: dict[str, Any] | None = None,
        *,
        timeout: float = 45,
        attempts: int = 3,
    ) -> dict[str, Any]:
        args = [
            "gcloud",
            service,
            operation,
            *self._encode_args(options),
            "--format=json",
        ]
        last: CommandFailure | None = None
        for attempt in range(attempts):
            try:
                completed = run(args, env=self.env, timeout=timeout)
                if not completed.stdout.strip():
                    return {}
                value = json.loads(completed.stdout)
                if not isinstance(value, dict):
                    return {"value": value}
                return value
            except json.JSONDecodeError as exc:
                raise HarnessError(f"gcloud returned non-JSON for {service} {operation}") from exc
            except CommandFailure as exc:
                last = exc
                transient = any(
                    marker in (exc.stderr + exc.stdout).lower()
                    for marker in ("connection", "temporarily", "timeout", "service unavailable", "internalerror")
                )
                if not transient or attempt + 1 >= attempts:
                    raise
                time.sleep(0.2 * (attempt + 1))
        assert last is not None
        raise last

    def safe_call(self, service: str, operation: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return self.call(service, operation, options)
        except CommandFailure as exc:
            return {"_error": exc.stderr or exc.stdout, "_returncode": exc.returncode}

    def file_call(
        self,
        service: str,
        operation: str,
        output_path: Path,
        options: dict[str, Any] | None = None,
        *,
        timeout: float = 90,
    ) -> dict[str, Any]:
        """Run gcloud operations whose response body requires a positional file."""
        args = [
            "gcloud",
            service,
            operation,
            *self._encode_args(options),
            str(output_path),
            "--format=json",
        ]
        completed = run(args, env=self.env, timeout=timeout)
        if not completed.stdout.strip():
            return {}
        value = json.loads(completed.stdout)
        return value if isinstance(value, dict) else {"value": value}


def _strings(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values if value})


def _is_orphan_service_log(name: str, rds_ids: set[str], cache_ids: set[str]) -> bool:
    rds_prefix, rds_suffix = "/aws/rds/instance/", "/error"
    if name.startswith(rds_prefix) and name.endswith(rds_suffix):
        owner = name[len(rds_prefix) : -len(rds_suffix)]
        return owner not in rds_ids
    cache_prefix, cache_suffix = "/aws/elasticache/cluster/", "/engine-log"
    if name.startswith(cache_prefix) and name.endswith(cache_suffix):
        owner = name[len(cache_prefix) : -len(cache_suffix)]
        return owner not in cache_ids
    return False


def _is_orphan_default_security_group(item: dict[str, Any], live_vpc_ids: set[str]) -> bool:
    return item.get("GroupName") == "default" and str(item.get("VpcId") or "") not in live_vpc_ids


def _is_orphan_main_route_table(item: dict[str, Any], live_vpc_ids: set[str]) -> bool:
    return (
        any(association.get("Main") is True for association in item.get("Associations", []))
        and str(item.get("VpcId") or "") not in live_vpc_ids
    )


def _inventory_call(
    client: GcpCli,
    service: str,
    operation: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an inventory read without silently accepting a partial snapshot."""
    response = client.safe_call(service, operation, options)
    if "_error" in response:
        detail = " ".join(str(response.get("_error") or "unknown error").split())[:300]
        raise HarnessError(f"incomplete inventory: {service} {operation}: {detail}")
    return response


def inventory(client: GcpCli) -> dict[str, list[str]]:
    """Return stable identifiers only; no timestamps/status fields."""
    project = client.project_id
    region = client.region
    result: dict[str, list[str]] = {}

    topics_resp = client.gcp_get(f"v1/projects/{project}/topics")
    result["pubsub.topics"] = _strings(
        item.get("name") for item in (topics_resp.get("topics") or []) if isinstance(item, dict)
    )
    subs_resp = client.gcp_get(f"v1/projects/{project}/subscriptions")
    result["pubsub.subscriptions"] = _strings(
        item.get("name") for item in (subs_resp.get("subscriptions") or []) if isinstance(item, dict)
    )
    buckets_resp = client.gcp_get(f"storage/v1/b?project={project}")
    result["storage.buckets"] = _strings(
        item.get("name") for item in (buckets_resp.get("items") or []) if isinstance(item, dict)
    )
    networks_resp = client.gcp_get(f"compute/v1/projects/{project}/global/networks")
    result["compute.networks"] = _strings(
        item.get("name") or item.get("selfLink")
        for item in (networks_resp.get("items") or [])
        if isinstance(item, dict)
    )
    run_resp = client.gcp_get(f"v2/projects/{project}/locations/{region}/services")
    result["run.services"] = _strings(
        item.get("name") for item in (run_resp.get("services") or []) if isinstance(item, dict)
    )
    fn_resp = client.gcp_get(f"v2/projects/{project}/locations/{region}/functions")
    result["cloudfunctions.functions"] = _strings(
        item.get("name") for item in (fn_resp.get("functions") or []) if isinstance(item, dict)
    )
    sql_resp = client.gcp_get(f"sql/v1beta4/projects/{project}/instances")
    result["sql.instances"] = _strings(
        item.get("name") for item in (sql_resp.get("items") or []) if isinstance(item, dict)
    )
    return result


def select_prefixed(value: dict[str, list[str]], prefix: str) -> dict[str, list[str]]:
    lowered = prefix.lower()
    if not lowered:
        return {key: list(items) for key, items in value.items()}
    return {key: [item for item in items if lowered in item.lower()] for key, items in value.items()}


def inventory_diff(before: dict[str, list[str]], after: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    keys = set(before) | set(after)
    return {
        key: {
            "added": sorted(set(after.get(key, [])) - set(before.get(key, []))),
            "removed": sorted(set(before.get(key, [])) - set(after.get(key, []))),
        }
        for key in sorted(keys)
        if set(before.get(key, [])) != set(after.get(key, []))
    }
