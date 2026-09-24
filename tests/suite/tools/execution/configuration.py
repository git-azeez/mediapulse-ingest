from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON file: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _runner_token() -> str:
    token_file = Path(_required_environment("CINDERROUTE_RUNNER_TOKEN_FILE"))
    try:
        return token_file.read_text(encoding="ascii").strip()
    except OSError:
        return ""


@dataclass(frozen=True)
class Config:
    tests_dir: Path
    submission_dir: Path
    logs_dir: Path
    evidence_dir: Path
    obligations_path: Path
    manifest_path: Path
    endpoint: str
    runner_socket: str
    runner_token: str
    region: str
    prefix: str
    seed: int
    deploy_timeout: int
    task_config: dict[str, Any]

    @property
    def infra_dir(self) -> Path:
        return self.submission_dir / "infra"

    @property
    def deploy_script(self) -> Path:
        return self.submission_dir / "deploy.sh"

    @property
    def destroy_script(self) -> Path:
        return self.submission_dir / "destroy.sh"

    @property
    def approved_images(self) -> set[str]:
        found: set[str] = set()
        for name in ("api_image", "processor_image", "projector_image", "relay_image", "archiver_image"):
            value = self.task_config.get(name)
            if value:
                found.add(str(value))
        return found

    @property
    def known_secrets(self) -> list[str]:
        values: list[str] = []
        for key, value in self.task_config.items():
            lowered = key.lower()
            if any(marker in lowered for marker in ("password", "secret", "token")) and isinstance(value, str):
                values.append(value)
        return [value for value in values if len(value) >= 4]


def from_environment(
    *,
    submission_dir: str | None = None,
    logs_dir: str | None = None,
    tests_dir: str | None = None,
) -> Config:
    package_tests = Path(__file__).resolve().parents[2]
    resolved_tests = Path(tests_dir).resolve() if tests_dir else package_tests
    resolved_submission = Path(
        submission_dir or os.environ.get("MEDIAPULSE_SUBMISSION_DIR") or _required_environment("CINDERROUTE_SUBMISSION_DIR")
    ).resolve()
    resolved_logs = Path(logs_dir or os.environ.get("MEDIAPULSE_LOGS_DIR") or _required_environment("CINDERROUTE_LOGS_DIR")).resolve()
    config_path = Path(os.environ.get("MEDIAPULSE_CONFIG") or _required_environment("CINDERROUTE_CONFIG"))
    task_config = _load_json(config_path)
    manifest_path = resolved_submission / "manifest.json"
    endpoint = str(task_config.get("gcp_endpoint_url") or task_config.get("gcp_endpoint_url") or "http://gcp:4588").rstrip("/")
    region = str(task_config.get("region") or "")
    prefix = str(task_config.get("resource_prefix") or "")
    seed_text = os.getenv("CINDERROUTE_TEST_SEED")
    seed = int(seed_text, 0) if seed_text else secrets.randbits(63)
    return Config(
        tests_dir=resolved_tests,
        submission_dir=resolved_submission,
        logs_dir=resolved_logs,
        evidence_dir=resolved_logs / "evidence",
        obligations_path=resolved_tests / "obligations.yaml",
        manifest_path=manifest_path,
        endpoint=endpoint,
        runner_socket=_required_environment("CINDERROUTE_RUNNER_SOCKET"),
        runner_token=_runner_token(),
        region=region,
        prefix=prefix,
        seed=seed,
        deploy_timeout=720,
        task_config=task_config,
    )
