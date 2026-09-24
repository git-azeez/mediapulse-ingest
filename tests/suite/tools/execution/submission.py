from __future__ import annotations

import hashlib
import stat
from pathlib import Path
from typing import Any

from ..cloud.gcp import inventory
from ..reporting.errors import HarnessError, SubmissionFailure
from ..trial import TrialContext


MAX_SUBMISSION_BYTES = 256 * 1024 * 1024
MAX_SUBMISSION_ENTRIES = 10_000
MAX_SUBMISSION_FILE_BYTES = 64 * 1024 * 1024
MAX_SUBMISSION_DEPTH = 32
HASH_CHUNK_BYTES = 1024 * 1024


def _validate_regular_tree(root: Path) -> str:
    if not root.is_dir():
        raise SubmissionFailure(f"submission directory does not exist: {root}")
    paths: list[Path] = []
    total_bytes = 0
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise SubmissionFailure(f"submission snapshot contains a symlink: {path.relative_to(root)}")
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise SubmissionFailure(f"submission snapshot contains a special file: {path.relative_to(root)}")
        paths.append(path)
        if len(paths) > MAX_SUBMISSION_ENTRIES:
            raise SubmissionFailure("submission exceeds 10000 filesystem entries")
        if len(path.relative_to(root).parts) > MAX_SUBMISSION_DEPTH:
            raise SubmissionFailure("submission exceeds directory depth 32")
        if path.is_file():
            size = path.stat().st_size
            if size > MAX_SUBMISSION_FILE_BYTES:
                raise SubmissionFailure("submission contains a file larger than 64 MiB")
            total_bytes += size
            if total_bytes > MAX_SUBMISSION_BYTES:
                raise SubmissionFailure("submission exceeds 256 MiB")
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode()
        is_file = path.is_file()
        digest.update(b"F" if is_file else b"D")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        if is_file:
            digest.update(path.stat().st_size.to_bytes(8, "big"))
            with path.open("rb") as stream:
                while chunk := stream.read(HASH_CHUNK_BYTES):
                    digest.update(chunk)
    return digest.hexdigest()


def run(ctx: TrialContext) -> dict[str, Any]:
    config = ctx.config
    actual_digest = _validate_regular_tree(config.submission_dir)
    for script in (config.deploy_script, config.destroy_script):
        if not script.is_file():
            raise SubmissionFailure(f"required script is missing: {script.name}")
    if not config.prefix:
        raise HarnessError("config.json must contain a non-empty randomized prefix")

    runner_health: dict[str, Any] = {}
    if ctx.runner is None:
        raise HarnessError("isolated execution runner is required")
    runner_health = ctx.runner.health()
    clone_digest = ctx.runner.prepare()
    if clone_digest != actual_digest:
        raise HarnessError("isolated runner clone does not match the collected submission")

    # A harmless list call distinguishes a broken control plane from a model
    # that simply did not create resources.
    response = ctx.gcp.gcp_get(f"v1/projects/{ctx.gcp.project_id}/topics")
    if "_error" in response:
        raise HarnessError(f"GCP control plane was unreachable before deploy: {response['_error'][:200]}")

    baseline = inventory(ctx.gcp)
    ctx.baseline = baseline
    ctx.facts["baseline_captured"] = True

    evidence = {
        "seed": config.seed,
        "prefix": config.prefix,
        "endpoint": config.endpoint,
        "baseline_source": "fresh-separate-verifier",
        "submission_digest": actual_digest,
        "runner_clone_digest": clone_digest,
        "separate_verifier": ctx.runner is not None,
        "privilege_separation": bool(runner_health),
        "runner_attestation": runner_health,
        "baseline": baseline,
    }
    ctx.evidence.json("preflight/integrity.json", evidence)
    return evidence
