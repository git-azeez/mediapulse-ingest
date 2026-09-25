output "prefix" { value = local.prefix }
output "project_id" { value = local.project }
output "region" { value = local.region }
output "gcp_endpoint_url" { value = local.ep }

output "api_image" { value = local.config.api_image }
output "processor_image" { value = local.config.processor_image }
output "relay_image" { value = local.config.relay_image }
output "archiver_image" { value = local.config.archiver_image }
output "api_image_id" { value = local.config.api_image_id }
output "processor_image_id" { value = local.config.processor_image_id }
output "relay_image_id" { value = local.config.relay_image_id }
output "archiver_image_id" { value = local.config.archiver_image_id }

output "lb_ip" { value = local.lb_ip }
output "lb_url" { value = local.lb_url }
output "forwarding_rule_id" { value = google_compute_global_forwarding_rule.api.id }
output "backend_service_id" { value = google_compute_backend_service.api.id }
output "serverless_neg_id" { value = google_compute_region_network_endpoint_group.serverless_neg.id }

output "cloud_run_service_id" { value = google_cloud_run_v2_service.api.id }
output "cloud_run_service_name" { value = google_cloud_run_v2_service.api.name }
output "cloud_run_service_uri" { value = google_cloud_run_v2_service.api.uri }
output "cloud_run_min_instance_count" { value = 2 }
output "cloud_run_max_instance_count" { value = 10 }

output "db_instance_name" { value = google_sql_database_instance.main.name }
output "db_private_ip" { value = google_sql_database_instance.main.private_ip_address }
output "db_port" { value = 5432 }
output "db_name" { value = google_sql_database.db.name }
output "db_secret_id" { value = google_secret_manager_secret.db_url.id }

output "topic_id" { value = google_pubsub_topic.main.id }
output "topic_name" { value = google_pubsub_topic.main.name }
output "subscription_id" { value = google_pubsub_subscription.push.id }
output "dlq_topic_id" { value = google_pubsub_topic.dlq.id }
output "dlq_subscription_id" { value = google_pubsub_subscription.dlq_pull.id }
output "max_delivery_attempts" { value = 5 }
output "rebuild_tasks_queue" { value = google_cloud_tasks_queue.rebuild.id }

output "firestore_database" { value = google_firestore_database.main.name }
output "firestore_collection" { value = "media_projections" }
output "bigquery_dataset" { value = google_bigquery_dataset.audit.id }

output "cache_engine" { value = "cloud-datastore" }
output "cache_datastore_namespace" { value = local.datastore_namespace }
output "cache_emulator_host" { value = "gcp:4588" }

output "auth_tenant_id" { value = google_identity_platform_tenant.main.name }
output "auth_resource_server_identifier" { value = "https://api.mediapulse.io" }
output "auth_issuer" { value = "${local.ep}/identitytoolkit/v3/relyingparty/${local.project}" }
output "auth_jwks_url" { value = local.jwks_url }
output "auth_token_endpoint" { value = "${local.ep}/oauth2/v4/token" }
output "read_client_email" { value = google_service_account.client_read.email }
output "write_client_email" { value = google_service_account.client_write.email }
output "admin_client_email" { value = google_service_account.client_admin.email }
output "read_client_secret" {
  value     = google_service_account_key.client_read.private_key
  sensitive = true
}
output "write_client_secret" {
  value     = google_service_account_key.client_write.private_key
  sensitive = true
}
output "admin_client_secret" {
  value     = google_service_account_key.client_admin.private_key
  sensitive = true
}

output "processor_id" { value = google_cloudfunctions2_function.processor.id }
output "relay_id" { value = google_cloudfunctions2_function.relay.id }
output "archiver_id" { value = google_cloudfunctions2_function.archiver.id }

output "relay_job_name" { value = google_cloud_scheduler_job.relay.name }
output "archiver_job_name" { value = google_cloud_scheduler_job.archiver.name }

output "audit_bucket" { value = google_storage_bucket.audit.name }
output "audit_prefix" { value = "events/" }

output "vpc_id" { value = google_compute_network.vpc.id }
output "ingress_subnet_id" { value = google_compute_subnetwork.ingress.id }
output "private_subnet_id" { value = google_compute_subnetwork.private.id }

output "api_service_account" { value = google_service_account.api.email }
output "processor_service_account" { value = google_service_account.processor.email }
output "relay_service_account" { value = google_service_account.relay.email }
output "archiver_service_account" { value = google_service_account.archiver.email }
output "scheduler_service_account" { value = google_service_account.scheduler.email }

output "kms_keyring_id" { value = google_kms_key_ring.kr.id }
output "kms_database_key_id" { value = google_kms_crypto_key.database.id }
output "kms_messaging_key_id" { value = google_kms_crypto_key.messaging.id }
output "kms_projection_key_id" { value = google_kms_crypto_key.projection.id }
output "kms_audit_key_id" { value = google_kms_crypto_key.audit.id }

output "logs_api" { value = google_logging_project_sink.api.name }
output "logs_processor" { value = google_logging_project_sink.processor.name }
output "logs_relay" { value = google_logging_project_sink.relay.name }
output "logs_archiver" { value = google_logging_project_sink.archiver.name }
