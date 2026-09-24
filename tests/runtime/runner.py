#!/usr/bin/env python3
"""Narrow execution broker for untrusted CinderRouter submissions.

The verifier oracle never imports or executes submission code.  It asks this
container to perform a fixed set of lifecycle/IaC operations and receives only
bounded logs and parsed JSON documents in return.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import signal
import socketserver
import stat
import subprocess
import tempfile
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path, PurePosixPath
from typing import Any


MAX_REQUEST_BYTES = 32 * 1024
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_RETURNED_OUTPUT_BYTES = MAX_OUTPUT_BYTES
MAX_COMMAND_SECONDS = 1200.0
MAX_SUBMISSION_BYTES = 256 * 1024 * 1024
MAX_SUBMISSION_ENTRIES = 10_000
MAX_SUBMISSION_FILE_BYTES = 64 * 1024 * 1024
MAX_SUBMISSION_DEPTH = 32
MAX_MANIFEST_BYTES = 1024 * 1024
HASH_CHUNK_BYTES = 1024 * 1024


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


class RequestError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status


class ExecutionRunner:
    def __init__(self) -> None:
        self.runner_root = Path(required_environment("CINDERROUTE_RUNNER_ROOT"))
        self.source = Path(required_environment("CINDERROUTE_RUNNER_SOURCE"))
        self.work = Path(required_environment("CINDERROUTE_RUNNER_WORK"))
        self.home = self.runner_root / "home"
        self.output_dir = self.runner_root / "output"
        self.config = Path("/workspace/config/config.json")
        for label, path in {
            "CINDERROUTE_RUNNER_ROOT": self.runner_root,
            "CINDERROUTE_RUNNER_SOURCE": self.source,
            "CINDERROUTE_RUNNER_WORK": self.work,
        }.items():
            if not path.is_absolute():
                raise RuntimeError(f"{label} must be an absolute path")
        if self.runner_root == Path("/"):
            raise RuntimeError("CINDERROUTE_RUNNER_ROOT must not be the filesystem root")
        if self.source == self.work:
            raise RuntimeError("runner source and work directories must be distinct")
        self.executor_uid = int(required_environment("CINDERROUTE_EXECUTOR_UID"))
        self.executor_gid = int(required_environment("CINDERROUTE_EXECUTOR_GID"))
        if self.executor_uid == 0 or self.executor_gid == 0:
            raise RuntimeError("executor UID/GID must be non-root")
        self.token_file = Path(required_environment("CINDERROUTE_RUNNER_TOKEN_FILE"))
        try:
            self.token = self.token_file.read_text(encoding="ascii").strip()
        except OSError as exc:
            raise RuntimeError("could not read the ephemeral runner token") from exc
        if len(self.token) < 32:
            raise RuntimeError("ephemeral runner token must contain at least 32 characters")
        self._operation_lock = threading.Lock()
        self._process_lock = threading.Lock()
        self._current: subprocess.Popen[bytes] | None = None
        self._prepared = False
        self._prepare_roots()
        self.attestation = self._attest_executor()

    def _prepare_roots(self) -> None:
        self.runner_root.mkdir(mode=0o755, parents=True, exist_ok=True)
        os.chown(self.runner_root, 0, 0)
        os.chmod(self.runner_root, 0o755)
        self.work.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        os.chown(self.work.parent, 0, 0)
        os.chmod(self.work.parent, 0o755)
        if not self.work.exists():
            self.work.mkdir(mode=0o700)
        os.chown(self.work, self.executor_uid, self.executor_gid)
        os.chmod(self.work, 0o700)
        self.home.mkdir(mode=0o700, exist_ok=True)
        os.chown(self.home, self.executor_uid, self.executor_gid)
        os.chmod(self.home, 0o700)
        self.output_dir.mkdir(mode=0o700, exist_ok=True)
        os.chown(self.output_dir, 0, 0)
        os.chmod(self.output_dir, 0o700)

    def _chown_executor_tree(self, root: Path) -> None:
        os.chown(root, self.executor_uid, self.executor_gid)
        for path in root.rglob("*"):
            os.chown(path, self.executor_uid, self.executor_gid, follow_symlinks=False)

    @property
    def binaries(self) -> list[str]:
        return [value for value in (shutil.which("terraform"), shutil.which("tofu")) if value]

    def _validate_source(self) -> None:
        if not self.source.is_dir():
            raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, "submission directory is missing")
        entries = 0
        total_bytes = 0
        for path in self.source.rglob("*"):
            rel_parts = path.relative_to(self.source).parts
            if ".terraform" in rel_parts or path.name == ".terraform.lock.hcl":
                continue
            try:
                metadata = path.lstat()
            except OSError as exc:
                raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, "submission tree is unreadable") from exc
            mode = metadata.st_mode
            if stat.S_ISLNK(mode):
                raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, "submission contains a symlink")
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, "submission contains a special file")
            if len(rel_parts) > MAX_SUBMISSION_DEPTH:
                raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, "submission exceeds directory depth 32")
            entries += 1
            if entries > MAX_SUBMISSION_ENTRIES:
                raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, "submission exceeds 10000 filesystem entries")
            if stat.S_ISREG(mode):
                if metadata.st_size > MAX_SUBMISSION_FILE_BYTES:
                    raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, "submission contains a file larger than 64 MiB")
                total_bytes += metadata.st_size
                if total_bytes > MAX_SUBMISSION_BYTES:
                    raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, "submission exceeds 256 MiB")

    def _digest(self, root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
            if ".terraform" in path.relative_to(root).parts or path.name == ".terraform.lock.hcl":
                continue
            relative = path.relative_to(root).as_posix().encode()
            kind = b"F" if path.is_file() else b"D"
            digest.update(kind)
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            if path.is_file():
                digest.update(path.stat().st_size.to_bytes(8, "big"))
                with path.open("rb") as stream:
                    while chunk := stream.read(HASH_CHUNK_BYTES):
                        digest.update(chunk)
        return digest.hexdigest()

    def _clone_source(self) -> None:
        self._validate_source()
        try:
            if self.work.exists():
                shutil.rmtree(self.work)
            shutil.copytree(
                self.source,
                self.work,
                symlinks=False,
                ignore=shutil.ignore_patterns(".terraform", ".terraform.lock.hcl"),
            )
            self._chown_executor_tree(self.work)
        except OSError as exc:
            if self.work.exists():
                shutil.rmtree(self.work, ignore_errors=True)
            raise RequestError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                f"submission could not be staged within runner limits: {type(exc).__name__}",
            ) from exc
        self._prepared = True

    def prepare(self) -> dict[str, Any]:
        self.cancel()
        with self._operation_lock:
            self._clone_source()
            return {"submission_sha256": self._digest(self.work)}

    def _ensure_prepared(self) -> None:
        if not self._prepared:
            self._clone_source()

    def _relative_path(self, raw: Any, *, default: str = ".") -> Path:
        value = str(raw or default)
        relative = PurePosixPath(value)
        if relative.is_absolute() or ".." in relative.parts:
            raise RequestError(HTTPStatus.BAD_REQUEST, "path must be relative to the submission")
        target = (self.work / Path(*relative.parts)).resolve()
        try:
            target.relative_to(self.work.resolve())
        except ValueError as exc:
            raise RequestError(HTTPStatus.BAD_REQUEST, "path escapes the submission") from exc
        return target

    def _binary(self, raw: Any) -> str:
        requested = str(raw or "")
        allowed = self.binaries
        by_name = {Path(item).name: item for item in allowed}
        if requested in allowed:
            return requested
        if requested in by_name:
            return by_name[requested]
        raise RequestError(HTTPStatus.BAD_REQUEST, "requested IaC binary is not installed")

    def _timeout(self, body: dict[str, Any], default: float) -> float:
        try:
            value = float(body.get("timeout", default))
        except (TypeError, ValueError) as exc:
            raise RequestError(HTTPStatus.BAD_REQUEST, "timeout must be numeric") from exc
        if value <= 0 or value > MAX_COMMAND_SECONDS:
            raise RequestError(HTTPStatus.BAD_REQUEST, "timeout is outside the runner limit")
        return value

    def _known_secrets(self) -> list[str]:
        try:
            value = json.loads(self.config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(value, dict):
            return []
        found: list[str] = []
        for key, item in value.items():
            if (
                isinstance(item, str)
                and len(item) >= 4
                and any(marker in key.lower() for marker in ("password", "secret", "token"))
            ):
                found.append(item)
        return found

    def _redact(self, value: str) -> str:
        for secret in self._known_secrets():
            value = value.replace(secret, "<redacted>")
        return value

    def _environment(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        # The runner lives on an internal Compose network by design.  Every
        # submission command therefore needs the bundled AWS provider mirror,
        # not only the runner's explicit init/validate action.  Otherwise a
        # perfectly valid deploy.sh will try registry.terraform.io and fail
        # before it can exercise the submitted infrastructure.
        offline_config = Path("/etc/terraformrc.offline")
        cli_config = offline_config if offline_config.is_file() else Path("/etc/terraformrc")
        gcp_endpoint = required_environment("GCP_ENDPOINT_URL").rstrip("/")
        environment = {
            "PATH": "/opt/venv/bin:/usr/local/bin:/usr/bin:/bin",
            "HOME": str(self.home),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "HTTP_PROXY": gcp_endpoint,
            "HTTPS_PROXY": gcp_endpoint,
            "http_proxy": gcp_endpoint,
            "https_proxy": gcp_endpoint,
            "NO_PROXY": "localhost,127.0.0.1,::1,runtime-setup,floci-gcp,gcp-gateway,gcp,floci",
            "no_proxy": "localhost,127.0.0.1,::1,runtime-setup,floci-gcp,gcp-gateway,gcp,floci",
            "GCE_METADATA_HOST": "127.0.0.1:1",
            "GCE_METADATA_ROOT": "127.0.0.1:1",
            "NO_GCE_CHECK": "true",
            "GCP_ENDPOINT_URL": gcp_endpoint,
            "GOOGLE_OAUTH_ACCESS_TOKEN": "floci-gcp-local-token",
            "PUBSUB_EMULATOR_HOST": required_environment("PUBSUB_EMULATOR_HOST"),
            "FIRESTORE_EMULATOR_HOST": required_environment("FIRESTORE_EMULATOR_HOST"),
            "DATASTORE_EMULATOR_HOST": required_environment("DATASTORE_EMULATOR_HOST"),
            "STORAGE_EMULATOR_HOST": required_environment("STORAGE_EMULATOR_HOST"),
            "SECRET_MANAGER_EMULATOR_HOST": required_environment("SECRET_MANAGER_EMULATOR_HOST"),
            "FIREBASE_AUTH_EMULATOR_HOST": required_environment("FIREBASE_AUTH_EMULATOR_HOST"),
            "GOOGLE_COMPUTE_CUSTOM_ENDPOINT": f"{gcp_endpoint}/compute/v1/",
            "GOOGLE_STORAGE_CUSTOM_ENDPOINT": f"{gcp_endpoint}/storage/v1/",
            "GOOGLE_PUBSUB_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_FIRESTORE_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_DATASTORE_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_SQL_CUSTOM_ENDPOINT": f"{gcp_endpoint}/sql/v1beta4/",
            "GOOGLE_CLOUD_RUN_CUSTOM_ENDPOINT": f"{gcp_endpoint}/run/v1/",
            "GOOGLE_CLOUD_RUN_V2_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v2/",
            "GOOGLE_CLOUDFUNCTIONS2_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v2/",
            "GOOGLE_CLOUD_SCHEDULER_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_CLOUD_TASKS_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v2/",
            "GOOGLE_SECRET_MANAGER_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_KMS_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_IAM_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_IAM_BETA_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_IAM_CREDENTIALS_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_RESOURCE_MANAGER_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_RESOURCE_MANAGER_V3_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v3/",
            "GOOGLE_CLOUD_RESOURCE_MANAGER_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_SERVICE_USAGE_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_IDENTITY_PLATFORM_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v2/",
            "GOOGLE_LOGGING_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v2/",
            "GOOGLE_MONITORING_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v3/",
            "GOOGLE_BIG_QUERY_CUSTOM_ENDPOINT": f"{gcp_endpoint}/bigquery/v2/",
            "GOOGLE_BIGQUERY_CUSTOM_ENDPOINT": f"{gcp_endpoint}/bigquery/v2/",
            "GOOGLE_EVENTARC_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "GOOGLE_ARTIFACT_REGISTRY_CUSTOM_ENDPOINT": f"{gcp_endpoint}/v1/",
            "CHECKPOINT_DISABLE": "1",
            "TF_IN_AUTOMATION": "1",
            "TF_INPUT": "0",
            "TF_CLI_CONFIG_FILE": str(cli_config),
        }
        environment.update(extra or {})
        return environment

    @staticmethod
    def _tail(stream: Any) -> str:
        stream.flush()
        size = stream.tell()
        stream.seek(max(0, size - MAX_RETURNED_OUTPUT_BYTES))
        prefix = "[output truncated]\n" if size > MAX_RETURNED_OUTPUT_BYTES else ""
        return prefix + stream.read().decode("utf-8", errors="replace")

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2.0)

    def _cleanup_uid_processes(self) -> None:
        """Remove submission descendants that escaped their original process group."""
        for sweep in range(8):
            victims: list[int] = []
            for entry in Path("/proc").iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    status_value = (entry / "status").read_text(encoding="utf-8", errors="replace")
                    uid_line = next(line for line in status_value.splitlines() if line.startswith("Uid:"))
                    real_uid = int(uid_line.split()[1])
                except (OSError, StopIteration, ValueError):
                    continue
                if real_uid == self.executor_uid:
                    victims.append(int(entry.name))
            if not victims:
                return
            selected_signal = signal.SIGTERM if sweep == 0 else signal.SIGKILL
            for pid in victims:
                try:
                    os.kill(pid, selected_signal)
                except ProcessLookupError:
                    pass
            time.sleep(0.05)
        remaining = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat().st_uid == self.executor_uid:
                    remaining.append(entry.name)
            except OSError:
                pass
        if remaining:
            raise RuntimeError(f"could not clean executor processes: {remaining[:8]}")

    def cancel(self) -> dict[str, Any]:
        with self._process_lock:
            process = self._current
        if process is not None:
            self._terminate(process)
        self._cleanup_uid_processes()
        return {"cancelled": process is not None}

    def _execute(
        self,
        args: list[str],
        *,
        cwd: Path,
        timeout: float,
        environment: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        exceeded_output = False
        timed_out = False
        with tempfile.TemporaryFile(dir=self.output_dir) as stdout, tempfile.TemporaryFile(
            dir=self.output_dir
        ) as stderr:
            wrapped_args = [
                "setpriv",
                f"--reuid={self.executor_uid}",
                f"--regid={self.executor_gid}",
                "--clear-groups",
                "--no-new-privs",
                "--inh-caps=-all",
                "--ambient-caps=-all",
                "--bounding-set=-all",
                "--",
                *args,
            ]
            process = subprocess.Popen(
                wrapped_args,
                cwd=cwd,
                env=self._environment(environment),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            with self._process_lock:
                if self._current is not None:
                    self._terminate(process)
                    raise RequestError(HTTPStatus.CONFLICT, "another runner command is active")
                self._current = process
            try:
                deadline = started + timeout
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        timed_out = True
                        self._terminate(process)
                        break
                    if stdout.tell() + stderr.tell() > MAX_OUTPUT_BYTES:
                        exceeded_output = True
                        self._terminate(process)
                        break
                    time.sleep(0.1)
                process.wait()
                stdout_value = self._redact(self._tail(stdout))
                stderr_value = self._redact(self._tail(stderr))
                if timed_out:
                    stderr_value += f"\nrunner terminated command after {timeout:.1f}s"
                if exceeded_output:
                    stderr_value += "\nrunner terminated command after output limit"
                return {
                    "args": [Path(args[0]).name, *args[1:]],
                    "returncode": int(process.returncode),
                    "stdout": stdout_value,
                    "stderr": stderr_value,
                    "duration_seconds": time.monotonic() - started,
                    "timed_out": timed_out,
                    "output_limited": exceeded_output,
                }
            finally:
                with self._process_lock:
                    if self._current is process:
                        self._current = None
                self._terminate(process)
                self._cleanup_uid_processes()

    def _attest_executor(self) -> dict[str, Any]:
        probe = """
import json, os, sys
broker_pid = int(sys.argv[1])
token_file, anchor, api_dir = sys.argv[2], sys.argv[3], sys.argv[4]
result = {"uid": os.getuid(), "gid": os.getgid(), "token_in_env": any("RUNNER_TOKEN" in key for key in os.environ)}
try:
    open(token_file, "rb").read(1)
    result["token_file_denied"] = False
except PermissionError:
    result["token_file_denied"] = True
try:
    open(f"/proc/{broker_pid}/environ", "rb").read(1)
    result["broker_environ_denied"] = False
except PermissionError:
    result["broker_environ_denied"] = True
try:
    os.kill(broker_pid, 0)
    result["broker_signal_denied"] = False
except PermissionError:
    result["broker_signal_denied"] = True
try:
    os.rename(anchor, anchor + ".moved")
    result["anchor_rename_denied"] = False
except PermissionError:
    result["anchor_rename_denied"] = True
try:
    os.listdir(api_dir)
    result["runner_api_denied"] = False
except PermissionError:
    result["runner_api_denied"] = True
print(json.dumps(result, sort_keys=True))
"""
        completed = self._execute(
            [
                "python3",
                "-c",
                probe,
                str(os.getpid()),
                str(self.token_file),
                str(self.work),
                str(Path(required_environment("CINDERROUTE_RUNNER_SOCKET")).parent),
            ],
            cwd=self.home,
            timeout=10,
        )
        if completed["returncode"] != 0:
            raise RuntimeError(f"executor isolation probe failed: {completed['stderr'][-400:]}")
        try:
            value = json.loads(completed["stdout"])
        except json.JSONDecodeError as exc:
            raise RuntimeError("executor isolation probe returned invalid JSON") from exc
        expected = {
            "uid": self.executor_uid,
            "gid": self.executor_gid,
            "token_in_env": False,
            "token_file_denied": True,
            "broker_environ_denied": True,
            "broker_signal_denied": True,
            "anchor_rename_denied": True,
            "runner_api_denied": True,
        }
        if value != expected:
            raise RuntimeError(f"executor isolation probe did not hold: {value}")
        return value

    def _require_script(self, name: str) -> Path:
        script = self.work / name
        if not script.is_file() or script.is_symlink():
            raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, f"{name} is missing")
        return script

    def _read_object(self, path: Path, label: str) -> dict[str, Any]:
        try:
            descriptor = os.open(
                path,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
            )
        except (FileNotFoundError, OSError) as exc:
            raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, f"{label} is missing or unsafe") from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, f"{label} is not a regular file")
            if metadata.st_size > MAX_MANIFEST_BYTES:
                raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, f"{label} exceeds 1 MiB")
            chunks: list[bytes] = []
            remaining = metadata.st_size
            while remaining:
                chunk = os.read(descriptor, min(remaining, 64 * 1024))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            if remaining or os.fstat(descriptor).st_size != metadata.st_size:
                raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, f"{label} changed while being read")
        finally:
            os.close(descriptor)
        try:
            value = json.loads(b"".join(chunks))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, f"{label} is not valid JSON") from exc
        if not isinstance(value, dict):
            raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, f"{label} is not a JSON object")
        stack: list[tuple[Any, int]] = [(value, 1)]
        nodes = 0
        while stack:
            item, depth = stack.pop()
            nodes += 1
            if depth > 64 or nodes > 100_000:
                raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, f"{label} exceeds JSON complexity limits")
            if isinstance(item, dict):
                stack.extend((nested, depth + 1) for nested in item.values())
            elif isinstance(item, list):
                stack.extend((nested, depth + 1) for nested in item)
        return value

    def _purge_stale_foreign_state(self) -> None:
        """If submission contains terraform.tfstate from the agent container's prefix/project, remove it before fresh verifier deploy."""
        try:
            cfg = json.loads(self.config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        expected_prefix = str(cfg.get("resource_prefix") or "").strip()
        expected_project = str(cfg.get("gcp_project_id") or "").strip()
        if not expected_prefix and not expected_project:
            return
        for state_file in list(self.work.rglob("terraform.tfstate")):
            try:
                raw = state_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if (expected_prefix and expected_prefix not in raw) or (expected_project and expected_project not in raw):
                for pattern in ("terraform.tfstate", "terraform.tfstate.backup", "*.tfplan", ".terraform.lock.hcl"):
                    for item in state_file.parent.glob(pattern):
                        item.unlink(missing_ok=True)
                (self.work / "manifest.json").unlink(missing_ok=True)

    def deploy(self, body: dict[str, Any]) -> dict[str, Any]:
        with self._operation_lock:
            self._ensure_prepared()
            self._purge_stale_foreign_state()
            completed = self._execute(
                ["bash", str(self._require_script("deploy.sh"))],
                cwd=self.work,
                timeout=self._timeout(body, 720),
            )
            manifest = self._read_object(self.work / "manifest.json", "manifest.json") if completed["returncode"] == 0 else {}
            return {"completed": completed, "manifest": manifest}

    def destroy(self, body: dict[str, Any]) -> dict[str, Any]:
        with self._operation_lock:
            self._ensure_prepared()
            completed = self._execute(
                ["bash", str(self._require_script("destroy.sh"))],
                cwd=self.work,
                timeout=self._timeout(body, 900),
            )
            return {"completed": completed}

    def tooling(self, body: dict[str, Any]) -> dict[str, Any]:
        with self._operation_lock:
            self._ensure_prepared()
            infra = self._relative_path(body.get("infra_dir"), default="infra")
            return {
                "binaries": self.binaries,
                "infra_is_directory": infra.is_dir(),
                "has_top_level_tf": infra.is_dir() and any(infra.glob("*.tf")),
            }

    def init_validate(self, body: dict[str, Any]) -> dict[str, Any]:
        with self._operation_lock:
            self._ensure_prepared()
            infra = self._relative_path(body.get("infra_dir"), default="infra")
            timeout = self._timeout(body, 120)
            requested = body.get("binaries") or self.binaries
            if not isinstance(requested, list):
                raise RequestError(HTTPStatus.BAD_REQUEST, "binaries must be a list")
            candidates = [self._binary(item) for item in requested]
            failures: list[str] = []
            last_init: dict[str, Any] | None = None
            last_validate: dict[str, Any] | None = None
            for candidate in candidates:
                offline = Path("/etc/terraformrc.offline")
                init_environment = {"TF_CLI_CONFIG_FILE": str(offline)} if offline.is_file() else None
                init = self._execute(
                    [candidate, "init", "-backend=false", "-input=false", "-no-color"],
                    cwd=infra,
                    timeout=timeout,
                    environment=init_environment,
                )
                if init["returncode"] != 0 and offline.is_file():
                    init = self._execute(
                        [candidate, "init", "-backend=false", "-input=false", "-no-color"],
                        cwd=infra,
                        timeout=timeout,
                    )
                last_init = init
                if init["returncode"] != 0:
                    failures.append(f"{Path(candidate).name} init: {(init['stderr'] or init['stdout'])[-400:]}")
                    continue
                validate = self._execute(
                    [candidate, "validate", "-json"], cwd=infra, timeout=timeout
                )
                last_validate = validate
                if validate["returncode"] == 0:
                    return {
                        "accepted": True,
                        "binary": candidate,
                        "binaries": self.binaries,
                        "init": init,
                        "validate": validate,
                    }
                failures.append(
                    f"{Path(candidate).name} validate: {(validate['stderr'] or validate['stdout'])[-400:]}"
                )
            return {
                "accepted": False,
                "binaries": self.binaries,
                "init": last_init,
                "validate": last_validate,
                "failures": failures,
            }

    def state(self, body: dict[str, Any]) -> dict[str, Any]:
        with self._operation_lock:
            self._ensure_prepared()
            infra = self._relative_path(body.get("infra_dir"), default="infra")
            binary = self._binary(body.get("binary"))
            args = [binary, "show", "-json"]
            state_path = infra / "terraform.tfstate"
            if state_path.is_file():
                args.append(str(state_path))
            completed = self._execute(args, cwd=infra, timeout=self._timeout(body, 90))
            document = self._parse_command_json(completed, "state")
            return {"completed": completed, "document": document}

    def _parse_command_json(self, completed: dict[str, Any], label: str) -> dict[str, Any]:
        if completed["returncode"] != 0:
            raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, f"{label} command failed")
        try:
            value = json.loads(completed["stdout"] or "{}")
        except json.JSONDecodeError as exc:
            raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, f"{label} command returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, f"{label} command returned non-object JSON")
        return value

    def configuration(self, body: dict[str, Any]) -> dict[str, Any]:
        with self._operation_lock:
            self._ensure_prepared()
            infra = self._relative_path(body.get("infra_dir"), default="infra")
            binary = self._binary(body.get("binary"))
            plan_path = self.work / ".cinderroute-configuration.tfplan"
            plan_path.unlink(missing_ok=True)
            completed = self._execute(
                [
                    binary,
                    "plan",
                    "-refresh=false",
                    "-lock=false",
                    "-input=false",
                    "-no-color",
                    "-detailed-exitcode",
                    "-out",
                    str(plan_path),
                ],
                cwd=infra,
                timeout=self._timeout(body, 180),
            )
            if completed["returncode"] not in {0, 2}:
                return {"completed": completed}
            try:
                shown = self._execute(
                    [binary, "show", "-json", str(plan_path)], cwd=infra, timeout=90
                )
                document = self._parse_command_json(shown, "configuration plan")
            finally:
                plan_path.unlink(missing_ok=True)
            configuration = document.get("configuration", {}).get("root_module")
            if not isinstance(configuration, dict):
                raise RequestError(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "Terraform plan JSON omitted parsed configuration",
                )
            return {"completed": completed, "configuration": configuration}

    def plan(self, body: dict[str, Any]) -> dict[str, Any]:
        with self._operation_lock:
            self._ensure_prepared()
            infra = self._relative_path(body.get("infra_dir"), default="infra")
            binary = self._binary(body.get("binary"))
            plan_path = self.work / ".cinderroute-detailed.tfplan"
            plan_path.unlink(missing_ok=True)
            completed = self._execute(
                [
                    binary,
                    "plan",
                    "-input=false",
                    "-no-color",
                    "-detailed-exitcode",
                    "-out",
                    str(plan_path),
                ],
                cwd=infra,
                timeout=self._timeout(body, 180),
            )
            document: dict[str, Any] = {}
            if completed["returncode"] in {0, 2}:
                try:
                    shown = self._execute(
                        [binary, "show", "-json", str(plan_path)], cwd=infra, timeout=90
                    )
                    document = self._parse_command_json(shown, "detailed plan")
                finally:
                    plan_path.unlink(missing_ok=True)
            else:
                plan_path.unlink(missing_ok=True)
            return {"completed": completed, "document": document}

    def manifest(self) -> dict[str, Any]:
        with self._operation_lock:
            self._ensure_prepared()
            return {"manifest": self._read_object(self.work / "manifest.json", "manifest.json")}


class RunnerHandler(BaseHTTPRequestHandler):
    server_version = "CinderRouteRunner/1"

    @property
    def runner(self) -> ExecutionRunner:
        return self.server.runner  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: HTTPStatus, value: dict[str, Any]) -> None:
        payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except BrokenPipeError:
            pass

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        return hmac.compare_digest(supplied, f"Bearer {self.runner.token}")

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise RequestError(HTTPStatus.BAD_REQUEST, "invalid Content-Length") from exc
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise RequestError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body is too large")
        try:
            value = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            raise RequestError(HTTPStatus.BAD_REQUEST, "request body is not valid JSON") from exc
        if not isinstance(value, dict):
            raise RequestError(HTTPStatus.BAD_REQUEST, "request body must be a JSON object")
        return value

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "broker_uid": os.getuid(),
                    "broker_root": os.getuid() == 0,
                    "executor": self.runner.attestation,
                    "active": self.runner._current is not None,
                },
            )
            return
        self._send(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._send(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        try:
            body = self._body()
            routes = {
                "/v1/prepare": lambda: self.runner.prepare(),
                "/v1/cancel": lambda: self.runner.cancel(),
                "/v1/deploy": lambda: self.runner.deploy(body),
                "/v1/destroy": lambda: self.runner.destroy(body),
                "/v1/tooling": lambda: self.runner.tooling(body),
                "/v1/iac/init-validate": lambda: self.runner.init_validate(body),
                "/v1/iac/state": lambda: self.runner.state(body),
                "/v1/iac/configuration": lambda: self.runner.configuration(body),
                "/v1/iac/plan": lambda: self.runner.plan(body),
                "/v1/manifest": lambda: self.runner.manifest(),
            }
            action = routes.get(self.path)
            if action is None:
                raise RequestError(HTTPStatus.NOT_FOUND, "not found")
            self._send(HTTPStatus.OK, {"ok": True, "result": action()})
        except RequestError as exc:
            self._send(exc.status, {"ok": False, "error": str(exc)})
        except BaseException as exc:
            self.runner.cancel()
            self._send(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": f"runner internal error: {type(exc).__name__}"},
            )


class RunnerUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, path: str, runner: ExecutionRunner):
        socketserver.UnixStreamServer.__init__(self, path, RunnerHandler)
        self.runner = runner
        self._request_slots = threading.BoundedSemaphore(4)

    def process_request(self, request: Any, client_address: Any) -> None:
        request.settimeout(5.0)
        if not self._request_slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._request_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()


def main() -> int:
    if os.getuid() != 0:
        raise RuntimeError("runner broker must start as root before dropping executor privileges")
    runner = ExecutionRunner()
    socket_path = required_environment("CINDERROUTE_RUNNER_SOCKET")
    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    server: Any = RunnerUnixServer(str(path), runner)
    os.chown(path, 0, int(required_environment("CINDERROUTE_RUNNER_AUTH_GID")))
    os.chmod(path, 0o660)

    def stop(_: int, __: Any) -> None:
        runner.cancel()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        runner.cancel()
        server.server_close()
        Path(socket_path).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
