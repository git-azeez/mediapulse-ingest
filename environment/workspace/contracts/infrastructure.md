# Infrastructure Contract

Declare every required Google Cloud Platform (GCP) resource in Terraform or OpenTofu and maintain it in `infra/terraform.tfstate`.

## Shared Rules

- Configure `hashicorp/google` and `hashicorp/google-beta` with `gcp_project_id`, `region`, and custom endpoints pointing to `gcp_endpoint_url` (`http://gcp:4588`) from `/workspace/config/config.json`.
- Prefix or label every managed resource with `resource_prefix` from `/workspace/config/config.json` and include the label `mediapulse_deployment=<resource_prefix>`.
- Manage only resources belonging to this deployment; do not modify or delete pre-existing baseline resources.

## Supported Floci-GCP Services Used

| Service | Terraform Resource Family | Responsibility |
|---|---|---|
| **Compute Engine & VPC** | `google_compute_network`, `google_compute_subnetwork`, `google_compute_firewall` | Custom VPC, ingress and private subnets, and port-level ingress rules |
| **Global External Load Balancer** | `google_compute_global_address`, `google_compute_region_network_endpoint_group`, `google_compute_backend_service`, `google_compute_url_map`, `google_compute_target_http_proxy`, `google_compute_global_forwarding_rule` | Public HTTP entry point routing via Serverless NEG to Cloud Run |
| **Cloud Run (v2)** | `google_cloud_run_v2_service` | Runs the HTTP API container with `min_instance_count >= 2` |
| **Cloud SQL for PostgreSQL** | `google_sql_database_instance`, `google_sql_database`, `google_sql_user` | Durable PostgreSQL 16 event store and transactional outbox |
| **Secret Manager** | `google_secret_manager_secret`, `google_secret_manager_secret_version` | Stores and versions database credentials |
| **Cloud Pub/Sub** | `google_pubsub_topic`, `google_pubsub_subscription` | Main event topic, push subscription to processor, and dead-letter topic/subscription |
| **Cloud Tasks** | `google_cloud_tasks_queue` | Rate-limited queue for projection rebuild tasks |
| **Cloud Functions (2nd gen)** | `google_cloudfunctions2_function` | Runs the Processor, Outbox Relay, and Audit Archiver workers |
| **Cloud Firestore** | `google_firestore_database` | Native-mode document store for media read projections and version timelines |
| **Cloud Datastore** | `google_firestore_index` or `google_datastore_index` | Low-latency entity cache (`collection = "MediaCache"` / kind) in front of Firestore |
| **Cloud Storage (GCS) & BigQuery** | `google_storage_bucket`, `google_bigquery_dataset`, `google_bigquery_table` | Private versioned NDJSON audit archive and analytics dataset |
| **Cloud Scheduler** | `google_cloud_scheduler_job` | Recurring OIDC cron triggers for the outbox relay (1m) and audit archiver (5m) |
| **Identity Platform / Firebase Auth** | `google_identity_platform_tenant`, `google_service_account_key` | Scoped JWT authentication (`read`, `write`, `admin`) |
| **Cloud IAM** | `google_service_account`, `google_project_iam_member`, `google_pubsub_topic_iam_member`, `google_pubsub_subscription_iam_member`, `google_storage_bucket_iam_member` | Per-component service accounts and least-privilege role bindings |
| **Cloud KMS** | `google_kms_key_ring`, `google_kms_crypto_key` | KeyRing and 4 separate CMEK keys (`database`, `messaging`, `projection`, `audit`) |
| **Cloud Logging & Monitoring** | `google_logging_project_bucket_config`, `google_logging_project_sink`, `google_monitoring_notification_channel` | 14-day structured log buckets and ops alerting channel |
