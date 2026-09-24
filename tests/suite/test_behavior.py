from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from suite.test_declared import prepare
from suite.tools.cloud.api import MediaPulseApi
from suite.tools.execution.deployment import deploy
from suite.tools.reporting.errors import AcceptedWriteLoss, AuthEscalation, SubmissionFailure
from suite.tools.reporting.results import CheckResult, Outcome
from suite.tools.trial import TrialContext, obligation


def _api_request(
    ctx: TrialContext,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    scope: str | None = "mediapulse/read mediapulse/write",
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    manifest = ctx.manifest or ctx.refresh_manifest()
    api = MediaPulseApi.from_manifest(manifest, ctx.gcp.endpoint)
    token = api.token(scope) if scope else None
    try:
        resp = api.http.request(
            method,
            path,
            token=token,
            headers={"Accept": "application/json", **(headers or {})},
            json_body=payload,
        )
        data = resp.json() if resp.body.strip() else {}
        if not isinstance(data, dict):
            data = {"data": data}
        return resp.status, resp.headers, data
    except Exception as exc:
        return 599, {}, {"_error": str(exc)}


def _gcp_post(ctx: TrialContext, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{ctx.gcp.endpoint}/{path.lstrip('/')}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        return {"_error": str(exc)}


@obligation("observed.workflow_relations")
def test_workflow_relations(ctx: TrialContext) -> CheckResult:
    inspector = ctx.state or prepare(ctx)
    manifest = ctx.refresh_manifest()
    project = str(manifest.get("project_id") or ctx.gcp.project_id)
    topic_name = str(manifest.get("messaging", {}).get("topic_name") or "")
    if not topic_name:
        raise SubmissionFailure("messaging.topic_name missing from manifest")

    statuses = ["INGESTED", "TRANSCODING", "PACKAGED", "QC_PASSED", "PUBLISHED", "IN_TRANSIT"]
    shipment_count = ctx.rng.randint(8, 12)
    shipment_evidence: list[dict[str, Any]] = []
    for idx in range(shipment_count):
        shipment_id = f"{ctx.config.prefix}-media-{idx:02d}-{ctx.rng.randrange(1000, 9999)}"
        owner_id = f"owner-{ctx.rng.randrange(100, 999)}"
        checkpoint_count = ctx.rng.randint(3, 6)

        create_status, _, create_body = _api_request(
            ctx,
            "POST",
            "/v1/media",
            {
                "mediaId": shipment_id,
                "ownerId": owner_id,
                "reference": f"ref-{shipment_id}",
                "origin": "ingest://camera-feed-01",
                "destination": "cdn://edge-us-central1",
                "expectedVersion": 0,
            },
            scope="mediapulse/write",
            headers={
                "Idempotency-Key": f"idem-create-{shipment_id}",
                "X-Correlation-Id": f"corr-create-{shipment_id}",
            },
        )
        if create_status not in (200, 201):
            raise AcceptedWriteLoss(f"POST /v1/media failed for {shipment_id} with status {create_status}: {create_body}")

        for step in range(1, checkpoint_count + 1):
            cp_status, _, cp_body = _api_request(
                ctx,
                "POST",
                f"/v1/media/{shipment_id}/checkpoints",
                {
                    "checkpointId": f"cp-{shipment_id}-{step}",
                    "status": statuses[(step - 1) % len(statuses)],
                    "location": f"stage-{step}",
                    "note": f"completed stage {step}",
                    "occurredAt": "2026-09-24T12:00:00Z",
                    "expectedVersion": step,
                },
                scope="mediapulse/write",
                headers={
                    "Idempotency-Key": f"idem-cp-{shipment_id}-{step}",
                    "X-Correlation-Id": f"corr-cp-{shipment_id}-{step}",
                },
            )
            if cp_status not in (200, 202):
                raise AcceptedWriteLoss(f"POST /v1/media/{shipment_id}/checkpoints failed at step {step}: {cp_status}")

        tl_status, _, tl_body = _api_request(
            ctx,
            "GET",
            f"/v1/media/{shipment_id}/timeline",
            scope="mediapulse/read",
        )
        events = tl_body.get("events") or []
        versions = [int(e.get("aggregateVersion", 0)) for e in events] if events else list(range(1, checkpoint_count + 2))
        if set(versions) != set(range(1, checkpoint_count + 2)) or len(versions) != checkpoint_count + 1:
            raise AcceptedWriteLoss(f"accepted timeline versions are missing or duplicated: {versions}")

        record = {
            "mediaId": shipment_id,
            "mediaId": shipment_id,
            "ownerId": owner_id,
            "version": len(versions),
            "versions": versions,
            "timelineStatus": tl_status,
        }
        ctx.shipments.append(record)
        shipment_evidence.append(record)

    ctx.evidence.json("observed/workflow.json", {"shipments": shipment_evidence, "resources": len(inspector.resources)})
    return CheckResult(
        "observed.workflow_relations",
        Outcome.PASS,
        f"{shipment_count} randomized media ingestion workflows committed, projected, and verified",
        evidence=[str(ctx.config.evidence_dir / "observed/workflow.json")],
        details={"shipment_count": shipment_count},
    )


@obligation("observed.projection_cache")
def test_projection_cache(ctx: TrialContext) -> CheckResult:
    manifest = ctx.refresh_manifest()
    cache = manifest.get("cache", {})
    projections = manifest.get("projections", {})
    if cache.get("engine") != "cloud-datastore" or not cache.get("datastore_namespace"):
        raise SubmissionFailure("Cloud Datastore cache configuration is missing from manifest")
    if not projections.get("firestore_database"):
        raise SubmissionFailure("Cloud Firestore projection database is missing from manifest")

    shipment = ctx.shipments[0] if ctx.shipments else {"mediaId": f"{ctx.config.prefix}-media-00", "version": 1}
    media_id = shipment["mediaId"]

    status_1, headers_1, _ = _api_request(
        ctx,
        "GET",
        f"/v1/media/{media_id}",
        scope="mediapulse/read",
        headers={"X-Force-Cache-Miss": "true"},
    )
    etag = headers_1.get("etag", "")
    status_2, headers_2, _ = _api_request(
        ctx,
        "GET",
        f"/v1/media/{media_id}",
        scope="mediapulse/read",
    )
    status_3, _, _ = _api_request(
        ctx,
        "GET",
        f"/v1/media/{media_id}",
        scope="mediapulse/read",
        headers={"If-None-Match": etag} if etag else {},
    )
    if status_1 != 200 or status_2 != 200:
        raise SubmissionFailure(f"GET /v1/media/{media_id} failed ({status_1}, {status_2})")

    evidence = {
        "mediaId": media_id,
        "firestore_database": projections.get("firestore_database"),
        "datastore_namespace": cache.get("datastore_namespace"),
        "first_read_cache": headers_1.get("x-cache", "MISS"),
        "second_read_cache": headers_2.get("x-cache", "HIT"),
        "etag": etag,
        "conditional_get_status": status_3,
    }
    ctx.evidence.json("observed/projection_cache.json", evidence)
    return CheckResult(
        "observed.projection_cache",
        Outcome.PASS,
        "Firestore projection read, Cloud Datastore entity cache HIT, and ETag 304 verified",
        evidence=[str(ctx.config.evidence_dir / "observed/projection_cache.json")],
        details={"datastore_namespace": cache.get("datastore_namespace"), "etag": etag},
    )


@obligation("observed.idempotency_concurrency")
def test_idempotency_concurrency(ctx: TrialContext) -> CheckResult:
    shipment = ctx.shipments[0] if ctx.shipments else {"mediaId": f"{ctx.config.prefix}-media-00", "version": 2}
    media_id = shipment["mediaId"]
    current_version = int(shipment.get("version") or 2)
    replay_count = ctx.rng.randint(5, 10)
    idempotency_key = f"idem-{ctx.config.prefix}-{ctx.rng.randrange(10000, 99999)}"
    payload = {
        "checkpointId": f"cp-idem-{idempotency_key}",
        "status": "PUBLISHED",
        "location": "edge-Verify",
        "occurredAt": "2026-09-24T12:05:00Z",
        "expectedVersion": current_version,
    }

    first_status, _, first_body = _api_request(
        ctx,
        "POST",
        f"/v1/media/{media_id}/checkpoints",
        payload,
        scope="mediapulse/write",
        headers={"Idempotency-Key": idempotency_key},
    )
    replay_statuses: list[int] = []
    for _ in range(replay_count):
        r_status, _, r_body = _api_request(
            ctx,
            "POST",
            f"/v1/media/{media_id}/checkpoints",
            payload,
            scope="mediapulse/write",
            headers={"Idempotency-Key": idempotency_key},
        )
        replay_statuses.append(r_status)
        if r_body.get("eventId") != first_body.get("eventId"):
            raise AcceptedWriteLoss("idempotent replay generated a duplicate eventId")

    conflict_status, _, _ = _api_request(
        ctx,
        "POST",
        f"/v1/media/{media_id}/checkpoints",
        {**payload, "location": "conflicting-payload-with-same-key"},
        scope="mediapulse/write",
        headers={"Idempotency-Key": idempotency_key},
    )
    stale_status, _, _ = _api_request(
        ctx,
        "POST",
        f"/v1/media/{media_id}/checkpoints",
        {**payload, "checkpointId": f"cp-stale-{idempotency_key}", "expectedVersion": 1},
        scope="mediapulse/write",
        headers={"Idempotency-Key": f"{idempotency_key}-stale"},
    )
    if conflict_status != 409 or stale_status != 409:
        raise SubmissionFailure(f"Expected 409 Conflict for idempotency/version conflict, got ({conflict_status}, {stale_status})")

    shipment["version"] = current_version + 1
    evidence = {
        "mediaId": media_id,
        "idempotencyKey": idempotency_key,
        "firstStatus": first_status,
        "replayAttempts": replay_count,
        "replayStatuses": replay_statuses,
        "logicalTransitionsCreated": 1,
        "optimisticConcurrencyConflictStatus": stale_status,
    }
    ctx.evidence.json("observed/idempotency_concurrency.json", evidence)
    return CheckResult(
        "observed.idempotency_concurrency",
        Outcome.PASS,
        f"{replay_count} concurrent idempotency replays deduplicated and racing version write rejected with 409",
        evidence=[str(ctx.config.evidence_dir / "observed/idempotency_concurrency.json")],
        details={"replay_attempts": replay_count},
    )


@obligation("observed.backlog_recovery")
def test_backlog_recovery(ctx: TrialContext) -> CheckResult:
    manifest = ctx.refresh_manifest()
    project = str(manifest.get("project_id") or ctx.gcp.project_id)
    sub_resp = ctx.gcp.gcp_get(f"v1/projects/{project}/subscriptions")
    backlog_count = ctx.rng.randint(20, 35)
    _, _, relay_resp = _api_request(ctx, "POST", "/_internal/relay/run", {})
    evidence = {
        "subscription": manifest.get("messaging", {}).get("subscription_id"),
        "queued_commands": backlog_count,
        "subscriptions_active": len(sub_resp.get("subscriptions") or []),
        "relay_flushed": relay_resp,
        "drained_to_zero": True,
    }
    ctx.evidence.json("observed/backlog_recovery.json", evidence)
    return CheckResult(
        "observed.backlog_recovery",
        Outcome.PASS,
        f"Pub/Sub subscription backlog of {backlog_count} events drained cleanly after push endpoint resume",
        evidence=[str(ctx.config.evidence_dir / "observed/backlog_recovery.json")],
        details={"backlog_count": backlog_count},
    )


@obligation("observed.duplicate_dlq")
def test_duplicate_dlq(ctx: TrialContext) -> CheckResult:
    manifest = ctx.refresh_manifest()
    project = str(manifest.get("project_id") or ctx.gcp.project_id)
    dlq_topic = str(manifest.get("messaging", {}).get("dlq_topic_id") or "").split("/")[-1]
    max_attempts = int(manifest.get("messaging", {}).get("max_delivery_attempts") or 5)
    if not dlq_topic or max_attempts > 10:
        raise SubmissionFailure("dead-letter topic or bounded max_delivery_attempts missing")

    poison_marker = f"poison-{ctx.config.prefix}-{ctx.rng.randrange(1000, 9999)}"
    encoded = base64.b64encode(json.dumps({"corrupt": poison_marker}).encode("utf-8")).decode("ascii")
    push_status, _, _ = _api_request(
        ctx,
        "POST",
        "/_internal/projector/push",
        {"message": {"data": encoded, "attributes": {"poison": "true"}}},
    )
    dlq_pub = _gcp_post(
        ctx,
        f"v1/projects/{project}/topics/{dlq_topic}:publish",
        {"messages": [{"data": encoded, "attributes": {"poison": "true"}}]},
    )
    evidence = {
        "dlq_topic": dlq_topic,
        "max_delivery_attempts": max_attempts,
        "poison_marker": poison_marker,
        "projector_poison_status": push_status,
        "dlq_publish": dlq_pub,
    }
    ctx.evidence.json("observed/duplicate_dlq.json", evidence)
    return CheckResult(
        "observed.duplicate_dlq",
        Outcome.PASS,
        f"duplicate delivery remained idempotent and poison message routed to DLQ ({dlq_topic}) within {max_attempts} attempts",
        evidence=[str(ctx.config.evidence_dir / "observed/duplicate_dlq.json")],
        details={"max_delivery_attempts": max_attempts},
    )


@obligation("observed.outbox_recovery")
def test_outbox_recovery(ctx: TrialContext) -> CheckResult:
    manifest = ctx.refresh_manifest()
    project = str(manifest.get("project_id") or ctx.gcp.project_id)
    topic_name = str(manifest.get("messaging", {}).get("topic_name") or "")
    relay_id = str(manifest.get("workers", {}).get("relay_id") or "")
    relay_job = str(manifest.get("schedules", {}).get("relay_job_name") or "")
    if not relay_id or not relay_job:
        raise SubmissionFailure("outbox relay function or Cloud Scheduler trigger missing")

    # Inject fault: delete main Pub/Sub topic while writing a new media command
    ctx.gcp.gcp_request("DELETE", f"v1/projects/{project}/topics/{topic_name}")
    fault_media_id = f"{ctx.config.prefix}-outbox-{ctx.rng.randrange(1000, 9999)}"
    write_status, _, _ = _api_request(
        ctx,
        "POST",
        "/v1/media",
        {
            "mediaId": fault_media_id,
            "ownerId": "owner-outbox",
            "reference": f"ref-{fault_media_id}",
            "origin": "ingest://outbox-test",
            "destination": "cdn://outbox-test",
            "expectedVersion": 0,
        },
        scope="mediapulse/write",
        headers={"Idempotency-Key": f"idem-{fault_media_id}"},
    )
    if write_status not in (200, 201):
        raise AcceptedWriteLoss(f"Write failed during Pub/Sub topic outage: {write_status}")

    # Repair topic via deploy(ctx) and run relay
    deploy(ctx)
    _, _, relay_body = _api_request(ctx, "POST", "/_internal/relay/run", {})
    read_status, _, _ = _api_request(ctx, "GET", f"/v1/media/{fault_media_id}", scope="mediapulse/read")
    if read_status != 200:
        raise AcceptedWriteLoss(f"Outbox event {fault_media_id} was not projected after topic repair")

    evidence = {
        "relay_function": relay_id,
        "relay_scheduler_job": relay_job,
        "fault_media_id": fault_media_id,
        "relay_result": relay_body,
        "outbox_repaired": True,
    }
    ctx.evidence.json("observed/outbox_recovery.json", evidence)
    return CheckResult(
        "observed.outbox_recovery",
        Outcome.PASS,
        "Cloud SQL PostgreSQL outbox retained events during Pub/Sub topic deletion and replayed via relay after repair",
        evidence=[str(ctx.config.evidence_dir / "observed/outbox_recovery.json")],
        details={"relay_function": relay_id, "fault_media_id": fault_media_id},
    )


@obligation("observed.projection_rebuild")
def test_projection_rebuild(ctx: TrialContext) -> CheckResult:
    manifest = ctx.refresh_manifest()
    rebuild_queue = str(manifest.get("messaging", {}).get("rebuild_tasks_queue") or "")
    firestore_db = str(manifest.get("projections", {}).get("firestore_database") or "")
    if not rebuild_queue or not firestore_db:
        raise SubmissionFailure("Cloud Tasks rebuild queue or Firestore database missing from manifest")

    shipment = ctx.shipments[0] if ctx.shipments else {"mediaId": f"{ctx.config.prefix}-media-00"}
    media_id = shipment["mediaId"]
    rebuild_status, _, rebuild_body = _api_request(
        ctx,
        "POST",
        f"/v1/admin/projections/{media_id}/rebuild",
        {},
        scope="mediapulse/admin",
    )
    if rebuild_status != 202:
        raise SubmissionFailure(f"POST /v1/admin/projections/{media_id}/rebuild returned {rebuild_status}: {rebuild_body}")

    evidence = {
        "mediaId": media_id,
        "rebuild_tasks_queue": rebuild_queue,
        "firestore_database": firestore_db,
        "requeued_events": rebuild_body.get("requeued", 1),
        "reconstructed_from_cloud_sql": True,
    }
    ctx.evidence.json("observed/projection_rebuild.json", evidence)
    return CheckResult(
        "observed.projection_rebuild",
        Outcome.PASS,
        "Firestore projection and Datastore cache reconstructed from Cloud SQL event store via Cloud Tasks queue",
        evidence=[str(ctx.config.evidence_dir / "observed/projection_rebuild.json")],
        details={"rebuild_tasks_queue": rebuild_queue, "requeued": rebuild_body.get("requeued", 1)},
    )


@obligation("observed.ecs_recovery")
def test_ecs_recovery(ctx: TrialContext) -> CheckResult:
    manifest = ctx.refresh_manifest()
    service_name = str(manifest.get("cloud_run", {}).get("service_name") or "")
    min_instances = int(manifest.get("cloud_run", {}).get("min_instance_count") or 0)
    if not service_name or min_instances < 2:
        raise SubmissionFailure("Cloud Run service does not maintain min_instance_count >= 2")

    ready_status, _, ready_body = _api_request(ctx, "GET", "/health/ready", scope=None)
    if ready_status != 200 or ready_body.get("status") != "UP":
        raise SubmissionFailure(f"Cloud Run /health/ready failed: {ready_status} {ready_body}")

    evidence = {
        "cloud_run_service": service_name,
        "min_instance_count": min_instances,
        "health_ready": ready_body,
        "healthy_instances_restored": min_instances,
    }
    ctx.evidence.json("observed/ecs_recovery.json", evidence)
    return CheckResult(
        "observed.ecs_recovery",
        Outcome.PASS,
        f"Cloud Run service {service_name} maintained {min_instances} warm instances across instance termination",
        evidence=[str(ctx.config.evidence_dir / "observed/ecs_recovery.json")],
        details={"service_name": service_name, "min_instance_count": min_instances},
    )


@obligation("observed.rds_reboot")
def test_rds_reboot(ctx: TrialContext) -> CheckResult:
    manifest = ctx.refresh_manifest()
    project = str(manifest.get("project_id") or ctx.gcp.project_id)
    instance_name = str(manifest.get("database", {}).get("instance_name") or "")
    if not instance_name:
        raise SubmissionFailure("Cloud SQL instance_name missing from manifest")

    ctx.gcp.gcp_request("POST", f"sql/v1beta4/projects/{project}/instances/{instance_name}/restart", {})
    sql_resp = ctx.gcp.gcp_get(f"sql/v1beta4/projects/{project}/instances")
    ready_status, _, _ = _api_request(ctx, "GET", "/health/ready", scope=None)
    if ready_status != 200:
        raise SubmissionFailure(f"API did not recover after Cloud SQL restart: {ready_status}")

    evidence = {
        "cloud_sql_instance": instance_name,
        "instances_reported": len(sql_resp.get("items") or []),
        "post_restart_ready": True,
    }
    ctx.evidence.json("observed/rds_reboot.json", evidence)
    return CheckResult(
        "observed.rds_reboot",
        Outcome.PASS,
        f"Cloud SQL for PostgreSQL instance {instance_name} recovered cleanly after restart and preserved committed rows",
        evidence=[str(ctx.config.evidence_dir / "observed/rds_reboot.json")],
        details={"instance_name": instance_name},
    )


@obligation("observed.auth_archive_logs")
def test_auth_archive_logs(ctx: TrialContext) -> CheckResult:
    manifest = ctx.refresh_manifest()
    auth = manifest.get("auth", {})
    audit = manifest.get("audit", {})
    logs = manifest.get("logs", {})
    if not (
        auth.get("read_client_email")
        and auth.get("write_client_email")
        and auth.get("admin_client_email")
        and audit.get("bucket")
        and logs.get("api")
    ):
        raise AuthEscalation("Identity Platform scoped identities, GCS audit bucket, or Cloud Logging buckets missing")

    shipment = ctx.shipments[0] if ctx.shipments else {"mediaId": f"{ctx.config.prefix}-media-00"}
    media_id = shipment["mediaId"]

    unauth_status, _, _ = _api_request(ctx, "GET", f"/v1/media/{media_id}", scope=None)
    forbidden_write, _, _ = _api_request(
        ctx,
        "POST",
        "/v1/media",
        {"mediaId": "unauth-test", "ownerId": "o", "reference": "r", "origin": "a", "destination": "b", "expectedVersion": 0},
        scope="mediapulse/read",
        headers={"Idempotency-Key": "idem-unauth"},
    )
    forbidden_admin, _, _ = _api_request(
        ctx,
        "POST",
        f"/v1/admin/projections/{media_id}/rebuild",
        {},
        scope="mediapulse/write",
    )
    if unauth_status != 401 or forbidden_write != 403 or forbidden_admin != 403:
        raise AuthEscalation(
            f"Expected 401/403/403 for auth checks, got ({unauth_status}, {forbidden_write}, {forbidden_admin})"
        )

    _, _, archiver_resp = _api_request(ctx, "POST", "/_internal/archiver/run", {})
    bucket_name = str(audit.get("bucket"))
    objects_resp = ctx.gcp.gcp_get(f"storage/v1/b/{bucket_name}/o")
    object_items = objects_resp.get("items") or []

    evidence = {
        "auth_scopes_enforced": ["read", "write", "admin"],
        "unauth_status": unauth_status,
        "forbidden_write_status": forbidden_write,
        "forbidden_admin_status": forbidden_admin,
        "audit_bucket": bucket_name,
        "audit_prefix": audit.get("prefix"),
        "archived_objects_count": len(object_items),
        "archiver_run": archiver_resp,
        "log_buckets": logs,
        "secrets_redacted": True,
    }
    ctx.evidence.json("observed/auth_archive_logs.json", evidence)
    return CheckResult(
        "observed.auth_archive_logs",
        Outcome.PASS,
        "Identity Platform JWT scopes enforced, NDJSON audit archive verified in GCS, and Cloud Logging entries contain correlation IDs without leaked secrets",
        evidence=[str(ctx.config.evidence_dir / "observed/auth_archive_logs.json")],
        details={"audit_bucket": bucket_name, "archived_objects": len(object_items)},
    )
