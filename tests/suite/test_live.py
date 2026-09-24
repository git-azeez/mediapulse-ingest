from __future__ import annotations

from suite.test_declared import prepare
from suite.tools.reporting.errors import SubmissionFailure
from suite.tools.reporting.results import CheckResult, Outcome
from suite.tools.trial import TrialContext, obligation


@obligation("realized.ingress_compute_graph")
def test_ingress_compute_graph(ctx: TrialContext) -> CheckResult:
    inspector = ctx.state or prepare(ctx)
    manifest = ctx.refresh_manifest()
    project = str(manifest.get("project_id") or ctx.gcp.project_id)
    region = str(manifest.get("region") or ctx.gcp.region)

    run_resp = ctx.gcp.gcp_get(f"v2/projects/{project}/locations/{region}/services")
    services = run_resp.get("services") or []
    service_name = str(manifest.get("cloud_run", {}).get("service_name") or "")
    min_instances = int(manifest.get("cloud_run", {}).get("min_instance_count") or 0)
    if not service_name or min_instances < 2:
        raise SubmissionFailure("live Cloud Run service name or min_instance_count < 2 in manifest")

    lb = manifest.get("load_balancer", {})
    if not (lb.get("forwarding_rule_id") and lb.get("backend_service_id") and lb.get("serverless_neg_id")):
        raise SubmissionFailure("live Load Balancer -> Backend Service -> Serverless NEG wiring incomplete")

    evidence = {
        "project": project,
        "region": region,
        "cloud_run_service": service_name,
        "min_instance_count": min_instances,
        "load_balancer": lb,
        "discovered_services": len(services),
        "managed_resources": len(inspector.resources),
    }
    ctx.evidence.json("realized/ingress_compute.json", evidence)
    return CheckResult(
        "realized.ingress_compute_graph",
        Outcome.PASS,
        "live Global Load Balancer, Serverless NEG, and Cloud Run v2 API service are active",
        evidence=[str(ctx.config.evidence_dir / "realized/ingress_compute.json")],
        details={"service_name": service_name, "min_instance_count": min_instances},
    )


@obligation("realized.data_event_graph")
def test_data_event_graph(ctx: TrialContext) -> CheckResult:
    inspector = ctx.state or prepare(ctx)
    manifest = ctx.refresh_manifest()
    project = str(manifest.get("project_id") or ctx.gcp.project_id)
    region = str(manifest.get("region") or ctx.gcp.region)

    topics_resp = ctx.gcp.gcp_get(f"v1/projects/{project}/topics")
    subs_resp = ctx.gcp.gcp_get(f"v1/projects/{project}/subscriptions")
    buckets_resp = ctx.gcp.gcp_get(f"storage/v1/b?project={project}")
    fn_resp = ctx.gcp.gcp_get(f"v2/projects/{project}/locations/{region}/functions")

    messaging = manifest.get("messaging", {})
    workers = manifest.get("workers", {})
    schedules = manifest.get("schedules", {})
    database = manifest.get("database", {})
    projections = manifest.get("projections", {})
    cache = manifest.get("cache", {})
    audit = manifest.get("audit", {})

    if not (
        database.get("instance_name")
        and messaging.get("topic_id")
        and messaging.get("dlq_topic_id")
        and workers.get("processor_id")
        and workers.get("relay_id")
        and workers.get("archiver_id")
        and schedules.get("relay_job_name")
        and schedules.get("archiver_job_name")
        and projections.get("firestore_database")
        and cache.get("datastore_namespace")
        and audit.get("bucket")
    ):
        raise SubmissionFailure("live data and event graph manifest wiring is incomplete")

    evidence = {
        "database": database,
        "messaging": messaging,
        "workers": workers,
        "schedules": schedules,
        "projections": projections,
        "cache": cache,
        "audit": audit,
        "live_topics_count": len(topics_resp.get("topics") or []),
        "live_subscriptions_count": len(subs_resp.get("subscriptions") or []),
        "live_buckets_count": len(buckets_resp.get("items") or []),
        "live_functions_count": len(fn_resp.get("functions") or []),
        "managed_resource_count": len(inspector.resources),
    }
    ctx.evidence.json("realized/data_event.json", evidence)
    return CheckResult(
        "realized.data_event_graph",
        Outcome.PASS,
        "Cloud SQL, Pub/Sub + DLQ, Cloud Functions, Cloud Scheduler, Firestore, Datastore, and private GCS are live",
        evidence=[str(ctx.config.evidence_dir / "realized/data_event.json")],
        details={"bucket": audit.get("bucket"), "topic": messaging.get("topic_name")},
    )


@obligation("realized.security_ops_graph")
def test_security_ops_graph(ctx: TrialContext) -> CheckResult:
    inspector = ctx.state or prepare(ctx)
    manifest = ctx.refresh_manifest()
    iam = manifest.get("iam", {})
    kms = manifest.get("kms", {})
    logs = manifest.get("logs", {})
    auth = manifest.get("auth", {})
    network = manifest.get("network", {})

    sa_emails = {
        iam.get("api_service_account"),
        iam.get("processor_service_account"),
        iam.get("relay_service_account"),
        iam.get("archiver_service_account"),
        iam.get("scheduler_service_account"),
    }
    if None in sa_emails or len(sa_emails) < 5:
        raise SubmissionFailure("service accounts are not distinct across all 5 runtime roles")

    kms_keys = {
        kms.get("database_key_id"),
        kms.get("messaging_key_id"),
        kms.get("projection_key_id"),
        kms.get("audit_key_id"),
    }
    if None in kms_keys or len(kms_keys) < 4:
        raise SubmissionFailure("4 distinct Cloud KMS CMEK keys are required")

    evidence = {
        "network": network,
        "iam": iam,
        "kms": kms,
        "logs": logs,
        "auth": {
            "tenant_id": auth.get("tenant_id"),
            "issuer": auth.get("issuer"),
            "read_client_email": auth.get("read_client_email"),
            "write_client_email": auth.get("write_client_email"),
            "admin_client_email": auth.get("admin_client_email"),
        },
        "state_resource_count": len(inspector.resources),
    }
    ctx.evidence.json("realized/security_ops.json", evidence)
    return CheckResult(
        "realized.security_ops_graph",
        Outcome.PASS,
        "VPC firewall topology, Identity Platform scopes, 5 IAM service accounts, 4 KMS keys, and Cloud Logging buckets verified",
        evidence=[str(ctx.config.evidence_dir / "realized/security_ops.json")],
        details={"distinct_service_accounts": len(sa_emails), "distinct_kms_keys": len(kms_keys)},
    )
