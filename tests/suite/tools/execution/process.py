from __future__ import annotations

import json
import os
import random
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

from ..reporting.errors import CommandFailure, DeadlineExceeded

T = TypeVar("T")


@dataclass
class Completed:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float

    def json(self) -> Any:
        return json.loads(self.stdout or "{}")


def redact(value: str, secrets: Iterable[str] = ()) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    return redacted


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 120,
    check: bool = True,
    secrets: Iterable[str] = (),
) -> Completed:
    started = time.monotonic()
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    process = subprocess.Popen(
        args,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )

    def terminate() -> None:
        if process.poll() is not None:
            process.communicate()
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.communicate(timeout=0.5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()

    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        terminate()
        raise DeadlineExceeded(f"command exceeded {timeout:.1f}s: {args[0]}") from exc
    except BaseException:
        # Per-obligation SIGALRM and verifier cancellation must not leave a
        # Terraform/AWS CLI child mutating later experiments.
        terminate()
        raise
    completed = Completed(
        args=args,
        returncode=process.returncode,
        stdout=redact(stdout, secrets),
        stderr=redact(stderr, secrets),
        duration_seconds=time.monotonic() - started,
    )
    if check and process.returncode != 0:
        raise CommandFailure(
            f"command failed ({completed.returncode}): {' '.join(args[:3])}",
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    return completed


def poll(
    probe: Callable[[], T],
    accept: Callable[[T], bool],
    *,
    timeout: float,
    initial_interval: float = 0.25,
    maximum_interval: float = 3.0,
    rng: random.Random | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> T:
    """Poll with bounded exponential backoff and deterministic optional jitter."""
    deadline = clock() + timeout
    interval = initial_interval
    last: T | None = None
    while True:
        last = probe()
        if accept(last):
            return last
        now = clock()
        if now >= deadline:
            raise DeadlineExceeded(f"condition not met within {timeout:.1f}s; last={last!r}")
        factor = (rng.uniform(0.85, 1.15) if rng else 1.0)
        sleeper(min(interval * factor, max(0.0, deadline - now)))
        interval = min(maximum_interval, interval * 1.7)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)
