from __future__ import annotations

import json
import http.client
import socket
from pathlib import Path
from typing import Any

from ..reporting.errors import CommandFailure, DeadlineExceeded, HarnessError, SubmissionFailure
from .process import Completed


MAX_RUNNER_RESPONSE_BYTES = 32 * 1024 * 1024


class RunnerClient:
    """Client for the isolated, action-whitelisted execution runner."""

    def __init__(self, socket_path: str, token: str, submission_dir: Path):
        if not socket_path:
            raise HarnessError("runner socket is not configured")
        self.socket_path = socket_path
        self.token = token
        self.submission_dir = submission_dir.resolve()
        if len(self.token) < 32:
            raise HarnessError("runner token is missing or too short")

    def _unix_exchange(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        timeout: float,
        *,
        authorized: bool,
    ) -> tuple[int, str, Any]:
        class UnixConnection(http.client.HTTPConnection):
            def connect(inner_self) -> None:
                connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                connection.settimeout(inner_self.timeout)
                connection.connect(self.socket_path)
                inner_self.sock = connection

        connection = UnixConnection("runner", timeout=timeout)
        payload = json.dumps(body or {}, separators=(",", ":")).encode() if method == "POST" else None
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            value = self._read_response(response)
            return response.status, response.reason, value
        finally:
            connection.close()

    @staticmethod
    def _raise_runner_status(status: int, reason: str, value: Any) -> None:
        detail = str(value.get("error") or reason) if isinstance(value, dict) else reason
        if status in {400, 404, 409}:
            raise HarnessError(f"runner protocol error: {detail}")
        if status == 422:
            raise SubmissionFailure(detail)
        raise HarnessError(f"runner HTTP {status}: {detail}")

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.submission_dir).as_posix()
        except ValueError as exc:
            raise HarnessError(f"runner path is outside the submission: {path}") from exc

    def _request(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        timeout: float = 30,
        cancel_on_error: bool = True,
    ) -> dict[str, Any]:
        try:
            status, reason, value = self._unix_exchange(
                "POST", path, body, timeout, authorized=True
            )
            if status >= 400:
                self._raise_runner_status(status, reason, value)
        except (TimeoutError, socket.timeout) as exc:
            if cancel_on_error:
                self.cancel()
            raise DeadlineExceeded(f"isolated runner request exceeded {timeout:.1f}s: {path}") from exc
        except (ConnectionError, OSError, http.client.HTTPException) as exc:
            if cancel_on_error:
                self.cancel()
            raise HarnessError(f"isolated runner socket is unreachable: {exc}") from exc
        except BaseException:
            if cancel_on_error:
                self.cancel()
            raise
        if not isinstance(value, dict) or value.get("ok") is not True or not isinstance(value.get("result"), dict):
            raise HarnessError("runner returned a malformed response")
        return value["result"]

    @staticmethod
    def _read_response(response: Any) -> Any:
        raw_length = response.headers.get("Content-Length")
        if raw_length:
            try:
                if int(raw_length) > MAX_RUNNER_RESPONSE_BYTES:
                    raise SubmissionFailure("runner result exceeds 32 MiB")
            except ValueError as exc:
                raise HarnessError("runner returned an invalid Content-Length") from exc
        payload = response.read(MAX_RUNNER_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RUNNER_RESPONSE_BYTES:
            raise SubmissionFailure("runner result exceeds 32 MiB")
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise HarnessError("runner returned invalid JSON") from exc

    @staticmethod
    def _completed(value: Any, *, check: bool = False) -> Completed:
        if not isinstance(value, dict):
            raise HarnessError("runner omitted command result")
        try:
            completed = Completed(
                args=[str(item) for item in value["args"]],
                returncode=int(value["returncode"]),
                stdout=str(value.get("stdout") or ""),
                stderr=str(value.get("stderr") or ""),
                duration_seconds=float(value["duration_seconds"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HarnessError("runner returned an invalid command result") from exc
        if value.get("timed_out") is True:
            raise DeadlineExceeded(
                f"isolated runner command exceeded its deadline: {completed.args[0]}",
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        if value.get("output_limited") is True:
            raise SubmissionFailure("submission command exceeded the runner output limit")
        if check and completed.returncode != 0:
            raise CommandFailure(
                f"runner command failed ({completed.returncode}): {' '.join(completed.args[:3])}",
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return completed

    def health(self) -> dict[str, Any]:
        try:
            status, reason, value = self._unix_exchange(
                "GET", "/healthz", None, 5, authorized=False
            )
            if status >= 400:
                self._raise_runner_status(status, reason, value)
        except (OSError, json.JSONDecodeError, http.client.HTTPException) as exc:
            raise HarnessError(f"isolated runner health check failed: {exc}") from exc
        executor = value.get("executor") if isinstance(value, dict) else None
        if (
            not isinstance(value, dict)
            or value.get("ok") is not True
            or value.get("broker_root") is not True
            or not isinstance(executor, dict)
            or int(executor.get("uid") or 0) == 0
            or any(
                executor.get(key) is not expected
                for key, expected in {
                    "token_in_env": False,
                    "token_file_denied": True,
                    "broker_environ_denied": True,
                    "broker_signal_denied": True,
                    "anchor_rename_denied": True,
                    "runner_api_denied": True,
                }.items()
            )
        ):
            raise HarnessError("isolated runner privilege-separation attestation failed")
        return value

    def prepare(self) -> str:
        value = self._request("/v1/prepare", timeout=30)
        digest = str(value.get("submission_sha256") or "")
        if len(digest) != 64:
            raise HarnessError("runner preparation omitted the submission digest")
        return digest

    def cancel(self) -> None:
        try:
            self._request("/v1/cancel", timeout=5, cancel_on_error=False)
        except BaseException:
            pass

    def deploy(self, timeout: float) -> tuple[Completed, dict[str, Any]]:
        value = self._request("/v1/deploy", {"timeout": timeout}, timeout=timeout + 10)
        completed = self._completed(value.get("completed"), check=True)
        manifest = value.get("manifest")
        if not isinstance(manifest, dict):
            raise SubmissionFailure("runner deploy did not produce manifest.json")
        return completed, manifest

    def destroy(self, timeout: float) -> Completed:
        value = self._request("/v1/destroy", {"timeout": timeout}, timeout=timeout + 10)
        return self._completed(value.get("completed"), check=False)

    def manifest(self) -> dict[str, Any]:
        value = self._request("/v1/manifest")
        manifest = value.get("manifest")
        if not isinstance(manifest, dict):
            raise SubmissionFailure("runner returned a malformed manifest")
        return manifest

    def tooling(self, infra_dir: Path) -> dict[str, Any]:
        return self._request("/v1/tooling", {"infra_dir": self._relative(infra_dir)})

    def init_validate(
        self,
        infra_dir: Path,
        binaries: list[str],
        timeout: float,
    ) -> tuple[Completed, Completed, str, list[str]]:
        value = self._request(
            "/v1/iac/init-validate",
            {"infra_dir": self._relative(infra_dir), "binaries": binaries, "timeout": timeout},
            timeout=(timeout * max(1, len(binaries)) * 3) + 10,
        )
        if value.get("accepted") is not True:
            failures = value.get("failures") or []
            raise SubmissionFailure(
                "neither Terraform nor OpenTofu accepted the submission: "
                + " | ".join(str(item) for item in failures)
            )
        init = self._completed(value.get("init"))
        validate = self._completed(value.get("validate"))
        binary = str(value.get("binary") or "")
        available = [str(item) for item in value.get("binaries") or []]
        if binary not in available:
            raise HarnessError("runner selected an unreported IaC binary")
        return init, validate, binary, available

    def state(self, infra_dir: Path, binary: str, timeout: float) -> dict[str, Any]:
        value = self._request(
            "/v1/iac/state",
            {"infra_dir": self._relative(infra_dir), "binary": binary, "timeout": timeout},
            timeout=timeout + 10,
        )
        document = value.get("document")
        if not isinstance(document, dict):
            raise SubmissionFailure("runner state response omitted Terraform/OpenTofu JSON")
        return document

    def configuration(
        self,
        infra_dir: Path,
        binary: str,
        timeout: float,
    ) -> tuple[Completed, dict[str, Any]]:
        value = self._request(
            "/v1/iac/configuration",
            {"infra_dir": self._relative(infra_dir), "binary": binary, "timeout": timeout},
            timeout=timeout + 110,
        )
        completed = self._completed(value.get("completed"))
        configuration = value.get("configuration")
        if completed.returncode not in {0, 2}:
            detail = (completed.stderr or completed.stdout)[-800:].strip()
            raise SubmissionFailure(f"could not obtain semantic Terraform configuration: {detail}")
        if not isinstance(configuration, dict):
            raise SubmissionFailure("Terraform plan JSON omitted its parsed configuration")
        return completed, configuration

    def detailed_plan(
        self,
        infra_dir: Path,
        binary: str,
        timeout: float,
    ) -> tuple[Completed, dict[str, Any]]:
        value = self._request(
            "/v1/iac/plan",
            {"infra_dir": self._relative(infra_dir), "binary": binary, "timeout": timeout},
            timeout=timeout + 110,
        )
        completed = self._completed(value.get("completed"))
        document = value.get("document") or {}
        if not isinstance(document, dict):
            raise HarnessError("runner detailed plan response is malformed")
        return completed, document
