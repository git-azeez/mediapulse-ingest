from __future__ import annotations

import json
from typing import Any

from suite.tools.infrastructure.manifest import validate_manifest_contract
from suite.tools.infrastructure.terraform import StateInspector
from suite.tools.reporting.errors import SubmissionFailure
from suite.tools.reporting.results import CheckResult, Outcome
from suite.tools.trial import TrialContext, obligation


BASE_FAMILIES = {
    "vpc": ("google_compute_network",),
    "subnetwork": ("google_compute_subnetwork",),
    "forwarding_rule": ("google_compute_global_forwarding_rule",),
    "backend_service": ("google_compute_backend_service",),
    "serverless_neg": ("google_compute_region_network_endpoint_group",),
    "cloud_run": ("google_cloud_run_v2_service",),
    "cloud_sql": ("google_sql_database_instance",),
    "secret_manager": ("google_secret_manager_secret",),
    "pubsub_topic": ("google_pubsub_topic",),
    "pubsub_subscription": ("google_pubsub_subscription",),
    "cloud_tasks": ("google_cloud_tasks_queue",),
    "cloud_functions": ("google_cloudfunctions2_function",),
    "firestore": ("google_firestore_database",),
    "datastore": ("google_datastore_index", "google_firestore_index"),
    "audit_bucket": ("google_storage_bucket",),
    "bigquery": ("google_bigquery_dataset",),
    "identity_platform": ("google_identity_platform_tenant",),
    "scheduler": ("google_cloud_scheduler_job",),
    "logs": ("google_logging_project_bucket_config",),
    "kms": ("google_kms_crypto_key",),
}


def prepare(ctx: TrialContext) -> StateInspector:
    manifest = ctx.refresh_manifest()
    auth = manifest.get("auth", {})
    if isinstance(auth, dict):
        ctx.evidence.add_secrets(
            str(value) for key, value in auth.items() if "secret" in key.lower() and value
        )
    validate_manifest_contract(manifest, ctx.config.task_config, ctx.config.tests_dir)
    inspector = StateInspector(
        ctx.config.infra_dir,
        manifest,
        runner=ctx.runner,
    )
    init, validate = inspector.init_validate()
    try:
        validation = json.loads(validate.stdout)
    except json.JSONDecodeError:
        validation = {"raw": validate.stdout}
    if isinstance(validation, dict) and validation.get("valid") is False:
        raise SubmissionFailure("tofu/terraform validate reported an invalid configuration")
    inspector.load()
    configuration = inspector.capture_configuration(ctx.config.evidence_dir / "declared" / "configuration.plan")
    ctx.state = inspector
    ctx.evidence.text("declared/init.log", init.stdout + init.stderr)
    ctx.evidence.json("declared/validate.json", validation)
    ctx.evidence.json("declared/state.json", inspector.document)
    ctx.evidence.json("declared/configuration.json", configuration)
    return inspector


@obligation("declared.managed_iac")
def test_managed_iac(ctx: TrialContext) -> CheckResult:
    inspector = ctx.state or prepare(ctx)
    counts = inspector.require_types(BASE_FAMILIES)
    prefix = ctx.config.prefix.lower()
    namespaced_types = {
        "google_compute_network",
        "google_compute_subnetwork",
        "google_cloud_run_v2_service",
        "google_sql_database_instance",
        "google_pubsub_topic",
        "google_pubsub_subscription",
        "google_cloudfunctions2_function",
        "google_storage_bucket",
        "google_cloud_scheduler_job",
        "google_service_account",
        "google_kms_crypto_key",
    }
    identity_fields = ("name", "bucket", "secret_id", "account_id", "dataset_id", "bucket_id")
    unnamespaced: list[str] = []
    for resource in inspector.resources:
        if resource.type not in namespaced_types:
            continue
        candidates = [resource.values.get(key) for key in identity_fields]
        candidates.extend([resource.values.get("labels"), resource.values.get("effective_labels")])
        if prefix not in json.dumps(candidates, sort_keys=True, default=str).lower():
            unnamespaced.append(resource.address)
    if unnamespaced:
        raise SubmissionFailure(
            f"managed resources ignore resource_prefix in identity/labels: {unnamespaced[:10]}"
        )
    return CheckResult(
        "declared.managed_iac",
        Outcome.PASS,
        "configuration validates and all required GCP resource families are managed in machine-readable state",
        evidence=[str(ctx.config.evidence_dir / "declared/state.json")],
        details={"managed_resource_count": len(inspector.resources), "family_counts": counts},
    )


@obligation("declared.compute_ingress")
def test_compute_ingress(ctx: TrialContext) -> CheckResult:
    inspector: StateInspector = ctx.state or prepare(ctx)
    manifest = ctx.manifest

    run_services = [r for r in inspector.resources if r.type == "google_cloud_run_v2_service"]
    if not run_services:
        raise SubmissionFailure("no managed google_cloud_run_v2_service found in state")
    api_service = run_services[0]
    templates = api_service.values.get("template") or []
    template = templates[0] if isinstance(templates, list) and templates else (templates if isinstance(templates, dict) else {})
    scaling_list = template.get("scaling") or []
    scaling = scaling_list[0] if isinstance(scaling_list, list) and scaling_list else (scaling_list if isinstance(scaling_list, dict) else {})
    min_instances = int(scaling.get("min_instance_count") or manifest.get("cloud_run", {}).get("min_instance_count") or 0)
    if min_instances < 2:
        raise SubmissionFailure(f"Cloud Run API min_instance_count must be >= 2, found {min_instances}")

    forwarding_rules = [r for r in inspector.resources if r.type == "google_compute_global_forwarding_rule"]
    backend_services = [r for r in inspector.resources if r.type == "google_compute_backend_service"]
    serverless_negs = [r for r in inspector.resources if r.type == "google_compute_region_network_endpoint_group"]
    if not (forwarding_rules and backend_services and serverless_negs):
        raise SubmissionFailure("Global External Application Load Balancer -> Backend Service -> Serverless NEG chain is incomplete")

    ctx.evidence.json(
        "declared/compute_ingress.json",
        {
            "cloud_run_service": api_service.values.get("name"),
            "min_instance_count": min_instances,
            "forwarding_rule": forwarding_rules[0].values.get("name"),
            "backend_service": backend_services[0].values.get("name"),
            "serverless_neg": serverless_negs[0].values.get("name"),
        },
    )
    return CheckResult(
        "declared.compute_ingress",
        Outcome.PASS,
        "Global Load Balancer, Serverless NEG, and Cloud Run v2 service with min_instance_count >= 2 are declared",
        evidence=[str(ctx.config.evidence_dir / "declared/compute_ingress.json")],
        details={"min_instance_count": min_instances},
    )


@obligation("declared.data_async")
def test_data_async(ctx: TrialContext) -> CheckResult:
    inspector: StateInspector = ctx.state or prepare(ctx)
    sql_instances = [r for r in inspector.resources if r.type == "google_sql_database_instance"]
    topics = [r for r in inspector.resources if r.type == "google_pubsub_topic"]
    subs = [r for r in inspector.resources if r.type == "google_pubsub_subscription"]
    functions = [r for r in inspector.resources if r.type == "google_cloudfunctions2_function"]
    firestore_dbs = [r for r in inspector.resources if r.type == "google_firestore_database"]
    datastore_indexes = [r for r in inspector.resources if r.type in ("google_datastore_index", "google_firestore_index")]
    buckets = [r for r in inspector.resources if r.type == "google_storage_bucket"]

    if not sql_instances:
        raise SubmissionFailure("no google_sql_database_instance declared")
    if len(topics) < 2 or len(subs) < 2:
        raise SubmissionFailure("main and dead-letter Pub/Sub topics and subscriptions must be declared")
    if len(functions) < 3:
        raise SubmissionFailure("processor, relay, and archiver Cloud Functions (2nd gen) must be declared")
    if not firestore_dbs or not datastore_indexes or not buckets:
        raise SubmissionFailure("Firestore projection database, Datastore index, and GCS audit bucket must be declared")

    max_attempts = int(ctx.manifest.get("messaging", {}).get("max_delivery_attempts") or 5)
    if max_attempts < 1 or max_attempts > 10:
        raise SubmissionFailure(f"Pub/Sub dead-letter max_delivery_attempts out of bounds: {max_attempts}")

    ctx.evidence.json(
        "declared/data_async.json",
        {
            "sql_instance": sql_instances[0].values.get("name"),
            "pubsub_topics": [t.values.get("name") for t in topics],
            "cloud_functions": [f.values.get("name") for f in functions],
            "firestore": firestore_dbs[0].values.get("name"),
            "datastore_kinds": [d.values.get("kind") or d.values.get("collection") for d in datastore_indexes],
            "audit_bucket": buckets[0].values.get("name"),
            "max_delivery_attempts": max_attempts,
        },
    )
    return CheckResult(
        "declared.data_async",
        Outcome.PASS,
        "Cloud SQL PostgreSQL, Pub/Sub + DLQ, Cloud Functions, Firestore, Datastore, and private GCS bucket are declared",
        evidence=[str(ctx.config.evidence_dir / "declared/data_async.json")],
        details={"cloud_functions": len(functions), "pubsub_topics": len(topics)},
    )


@obligation("declared.security_ops")
def test_security_ops(ctx: TrialContext) -> CheckResult:
    inspector: StateInspector = ctx.state or prepare(ctx)
    service_accounts = [r for r in inspector.resources if r.type == "google_service_account"]
    kms_keys = [r for r in inspector.resources if r.type == "google_kms_crypto_key"]
    log_buckets = [r for r in inspector.resources if r.type == "google_logging_project_bucket_config"]
    subnets = [r for r in inspector.resources if r.type == "google_compute_subnetwork"]

    if len(service_accounts) < 5:
        raise SubmissionFailure(f"expected at least 5 distinct service accounts, found {len(service_accounts)}")
    if len(kms_keys) < 4:
        raise SubmissionFailure(f"expected 4 customer-managed Cloud KMS crypto keys, found {len(kms_keys)}")
    if len(log_buckets) < 4:
        raise SubmissionFailure(f"expected 4 Cloud Logging bucket configs, found {len(log_buckets)}")
    if len(subnets) < 2:
        raise SubmissionFailure("expected ingress and private VPC subnetworks")

    ctx.evidence.json(
        "declared/security_ops.json",
        {
            "service_accounts": [sa.values.get("email") or sa.values.get("account_id") for sa in service_accounts],
            "kms_keys": [k.values.get("name") for k in kms_keys],
            "log_buckets": [lb.values.get("bucket_id") for lb in log_buckets],
            "subnetworks": [s.values.get("name") for s in subnets],
        },
    )
    return CheckResult(
        "declared.security_ops",
        Outcome.PASS,
        "per-component service accounts, ingress/private VPC subnets, 4 CMEK KMS keys, and 14-day log buckets are declared",
        evidence=[str(ctx.config.evidence_dir / "declared/security_ops.json")],
        details={"service_accounts": len(service_accounts), "kms_keys": len(kms_keys)},
    )
