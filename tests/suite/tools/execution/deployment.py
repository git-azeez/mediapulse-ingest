from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Callable

from ..reporting.errors import CommandFailure, HarnessError, SubmissionFailure
from .process import Completed, poll

if TYPE_CHECKING:
    from ..trial import TrialContext


def deploy(ctx: TrialContext, *, timeout: int | None = None) -> Completed:
    if not ctx.config.deploy_script.is_file():
        raise SubmissionFailure("deploy.sh is missing")
    effective_timeout = timeout or ctx.config.deploy_timeout
    if ctx.runner is None:
        raise HarnessError("isolated execution runner is required")
    try:
        completed, manifest = ctx.runner.deploy(effective_timeout)
    except CommandFailure as exc:
        ctx.evidence.text("lifecycle/deploy.log", (exc.stdout or "") + (exc.stderr or ""))
        raise
    ctx.manifest = manifest
    ctx.evidence.text("lifecycle/deploy.log", completed.stdout + completed.stderr)
    return completed


def destroy(ctx: TrialContext, *, timeout: int = 900) -> Completed:
    if not ctx.config.destroy_script.is_file():
        raise SubmissionFailure("destroy.sh is missing")
    if ctx.runner is None:
        raise HarnessError("isolated execution runner is required")
    completed = ctx.runner.destroy(timeout)
    ctx.evidence.text("lifecycle/destroy.log", completed.stdout + completed.stderr)
    return completed


def subscription_message_count(ctx: TrialContext, subscription_id: str) -> int:
    """Return the approximate number of undelivered messages on a Pub/Sub subscription."""
    project = ctx.manifest.get("project_id") or ctx.gcp.project_id
    resp = ctx.gcp.gcp_get(
        f"v1/projects/{project}/subscriptions/{subscription_id}"
    )
    return int(resp.get("messageCount") or 0)


def wait_subscription_drain(
    ctx: TrialContext,
    subscription_id: str,
    predicate: Callable[[int], bool],
    *,
    timeout: float,
) -> int:
    """Poll a Pub/Sub subscription until predicate is satisfied."""
    return poll(
        lambda: subscription_message_count(ctx, subscription_id),
        predicate,
        timeout=timeout,
        rng=ctx.rng,
    )


def list_firestore_documents(ctx: TrialContext, collection: str) -> list[dict[str, Any]]:
    """Return documents from a Firestore collection via the REST emulator."""
    project = ctx.manifest.get("project_id") or ctx.gcp.project_id
    database = ctx.manifest.get("projections", {}).get("firestore_database", "(default)")
    resp = ctx.gcp.gcp_get(
        f"v1/projects/{project}/databases/{database}/documents/{collection}"
    )
    return list(resp.get("documents") or [])


def invoke_cloud_function(
    ctx: TrialContext, function_url: str, payload: dict[str, Any], label: str
) -> dict[str, Any]:
    """HTTP-invoke a Cloud Function (2nd gen) by its trigger URL."""
    import urllib.request

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        function_url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90.0) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            result = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        raise SubmissionFailure(f"{label} Cloud Function invocation failed: {exc}") from exc
    if isinstance(result, dict) and result.get("error"):
        raise SubmissionFailure(f"{label} Cloud Function returned error: {result}")
    return result if isinstance(result, dict) else {"value": result}
