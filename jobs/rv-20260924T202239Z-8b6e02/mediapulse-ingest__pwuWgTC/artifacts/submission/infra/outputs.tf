output "load_balancer_ip_address" {
  value = google_compute_global_address.lb.address
}
output "load_balancer_url" {
  value = "http://${google_compute_global_address.lb.address}"
}
output "load_balancer_connect_url" {
  value = var.gcp_endpoint_url
}
output "forwarding_rule_id" {
  value = google_compute_global_forwarding_rule.api.id
}
output "backend_service_id" {
  value = google_compute_backend_service.api.id
}
output "serverless_neg_id" {
  value = google_compute_region_network_endpoint_group.serverless.id
}

output "cloud_run_service_id" {
  value = google_cloud_run_v2_service.api.id
}
output "cloud_run_service_name" {
  value = google_cloud_run_v2_service.api.name
}
output "cloud_run_service_uri" {
  value = google_cloud_run_v2_service.api.uri
}
output "cloud_run_min_instance_count" {
  value = google_cloud_run_v2_service.api.template[0].scaling[0].min_instance_count
}
output "cloud_run_max_instance_count" {
  value = google_cloud_run_v2_service.api.template[0].scaling[0].max_instance_count
}

output "database_instance_name" {
  value = google_sql_database_instance.main.name
}
output "database_private_ip" {
  value = google_sql_database_instance.main.private_ip_address
}
output "database_port" {
  value = 5432
}
output "database_name" {
  value = google_sql_database.main.name
}
output "database_secret_id" {
  value = google_secret_manager_secret.db_url.id
}

output "messaging_topic_id" {
  value = google_pubsub_topic.main.id
}
output "messaging_topic_name" {
  value = google_pubsub_topic.main.name
}
output "messaging_subscription_id" {
  value = google_pubsub_subscription.processor.id
}
output "messaging_dlq_topic_id" {
  value = google_pubsub_topic.dlq.id
}
output "messaging_dlq_subscription_id" {
  value = google_pubsub_subscription.dlq.id
}
output "messaging_max_delivery_attempts" {
  value = google_pubsub_subscription.processor.dead_letter_policy[0].max_delivery_attempts
}
output "messaging_rebuild_tasks_queue" {
  value = google_cloud_tasks_queue.rebuild.id
}

output "projections_firestore_database" {
  value = google_firestore_database.main.name
}
output "projections_collection" {
  value = "media_projections"
}
output "projections_bigquery_dataset" {
  value = google_bigquery_dataset.audit.id
}

output "cache_engine" {
  value = "cloud-datastore"
}
output "cache_datastore_namespace" {
  value = local.datastore_namespace
}
output "cache_emulator_host" {
  # host:port of the Floci-GCP Datastore endpoint
  value = replace(replace(var.gcp_endpoint_url, "http://", ""), "https://", "")
}

output "auth_tenant_id" {
  value = google_identity_platform_tenant.main.name
}
output "auth_resource_server_identifier" {
  value = "https://api.mediapulse.io"
}
output "auth_issuer" {
  value = "${var.gcp_endpoint_url}/identitytoolkit/v3/relyingparty/${var.project_id}"
}
output "auth_jwks_url" {
  value = "${var.gcp_endpoint_url}/robot/v1/metadata/jwk/securetoken@system.gserviceaccount.com"
}
output "auth_token_endpoint" {
  value = "${var.gcp_endpoint_url}/oauth2/v4/token"
}
output "auth_read_client_email" {
  value = google_service_account.client_read.email
}
output "auth_write_client_email" {
  value = google_service_account.client_write.email
}
output "auth_admin_client_email" {
  value = google_service_account.client_admin.email
}
output "auth_read_client_id" {
  value = google_service_account.client_read.email
}
output "auth_write_client_id" {
  value = google_service_account.client_write.email
}
output "auth_admin_client_id" {
  value = google_service_account.client_admin.email
}
output "auth_read_client_secret" {
  value     = google_service_account_key.client_read.private_key
  sensitive = true
}
output "auth_write_client_secret" {
  value     = google_service_account_key.client_write.private_key
  sensitive = true
}
output "auth_admin_client_secret" {
  value     = google_service_account_key.client_admin.private_key
  sensitive = true
}

output "workers_processor_id" {
  value = google_cloudfunctions2_function.processor.id
}
output "workers_relay_id" {
  value = google_cloudfunctions2_function.relay.id
}
output "workers_archiver_id" {
  value = google_cloudfunctions2_function.archiver.id
}

output "schedules_relay_job_name" {
  value = google_cloud_scheduler_job.relay.name
}
output "schedules_archiver_job_name" {
  value = google_cloud_scheduler_job.archiver.name
}

output "audit_bucket" {
  value = google_storage_bucket.audit.name
}
output "audit_prefix" {
  value = "events/"
}

output "network_vpc_id" {
  value = google_compute_network.vpc.id
}
output "network_ingress_subnet_id" {
  value = google_compute_subnetwork.ingress.id
}
output "network_private_subnet_id" {
  value = google_compute_subnetwork.private.id
}

output "iam_api_service_account" {
  value = google_service_account.api.email
}
output "iam_processor_service_account" {
  value = google_service_account.processor.email
}
output "iam_relay_service_account" {
  value = google_service_account.relay.email
}
output "iam_archiver_service_account" {
  value = google_service_account.archiver.email
}
output "iam_scheduler_service_account" {
  value = google_service_account.scheduler.email
}

output "kms_keyring_id" {
  value = google_kms_key_ring.main.id
}
output "kms_database_key_id" {
  value = google_kms_crypto_key.database.id
}
output "kms_messaging_key_id" {
  value = google_kms_crypto_key.messaging.id
}
output "kms_projection_key_id" {
  value = google_kms_crypto_key.projection.id
}
output "kms_audit_key_id" {
  value = google_kms_crypto_key.audit.id
}

output "logs_api" {
  value = google_logging_project_sink.api.id
}
output "logs_processor" {
  value = google_logging_project_sink.processor.id
}
output "logs_relay" {
  value = google_logging_project_sink.relay.id
}
output "logs_archiver" {
  value = google_logging_project_sink.archiver.id
}
