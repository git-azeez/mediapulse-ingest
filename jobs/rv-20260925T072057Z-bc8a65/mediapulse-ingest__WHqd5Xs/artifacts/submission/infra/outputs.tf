# Outputs consumed by deploy.sh to assemble manifest.json

output "prefix" { value = local.prefix }
output "project_id" { value = local.project_id }
output "region" { value = local.region }
output "gcp_endpoint_url" { value = local.gcp_endpoint }

output "approved_images" {
  value = {
    api       = local.cfg.api_image
    processor = local.cfg.processor_image
    relay     = local.cfg.relay_image
    archiver  = local.cfg.archiver_image
  }
}

# Load balancer
output "lb_ip_address" { value = google_compute_global_address.lb_ip.address }
output "lb_url" { value = "http://${google_compute_global_address.lb_ip.address}" }
output "lb_connect_url" { value = "http://${google_compute_global_address.lb_ip.address}" }
output "forwarding_rule_id" { value = google_compute_global_forwarding_rule.api_fr.id }
output "backend_service_id" { value = google_compute_backend_service.api_backend.id }
output "serverless_neg_id" { value = google_compute_region_network_endpoint_group.api_neg.id }

# Cloud Run
output "cloud_run_service_id" { value = google_cloud_run_v2_service.api.id }
output "cloud_run_service_name" { value = google_cloud_run_v2_service.api.name }
output "cloud_run_service_uri" { value = google_cloud_run_v2_service.api.uri }
output "cloud_run_min_instance_count" { value = google_cloud_run_v2_service.api.template[0].scaling[0].min_instance_count }
output "cloud_run_max_instance_count" { value = google_cloud_run_v2_service.api.template[0].scaling[0].max_instance_count }

# Database
output "db_instance_name" { value = google_sql_database_instance.main.name }
output "db_private_ip" { value = google_sql_database_instance.main.private_ip_address }
output "db_port" { value = 5432 }
output "db_name" { value = google_sql_database.db.name }
output "db_secret_id" { value = google_secret_manager_secret.db_url.id }

# Messaging
output "topic_id" { value = google_pubsub_topic.main.id }
output "topic_name" { value = google_pubsub_topic.main.name }
output "subscription_id" { value = google_pubsub_subscription.processor_push.id }
output "dlq_topic_id" { value = google_pubsub_topic.dlq.id }
output "dlq_subscription_id" { value = google_pubsub_subscription.dlq.id }
output "max_delivery_attempts" { value = 5 }
output "rebuild_tasks_queue" { value = google_cloud_tasks_queue.rebuild.id }

# Projections
output "firestore_database" { value = google_firestore_database.main.name }
output "projections_collection" { value = "media_projections" }
output "bigquery_dataset" { value = google_bigquery_dataset.audit.id }

# Cache
output "cache_engine" { value = "cloud-datastore" }
output "cache_datastore_namespace" { value = local.datastore_namespace }
output "cache_emulator_host" { value = "gcp:4588" }

# Auth
output "auth_tenant_id" { value = google_identity_platform_tenant.main.name }
output "auth_resource_server_identifier" { value = "https://api.mediapulse.io" }
output "auth_issuer" { value = "${local.gcp_endpoint}/identitytoolkit/v3/relyingparty/${local.project_id}" }
output "auth_jwks_url" { value = "${local.gcp_endpoint}/robot/v1/metadata/jwk/securetoken@system.gserviceaccount.com" }
output "auth_token_endpoint" { value = "${local.gcp_endpoint}/oauth2/v4/token" }

output "read_client_email" { value = google_service_account.client_read.email }
output "write_client_email" { value = google_service_account.client_write.email }
output "admin_client_email" { value = google_service_account.client_admin.email }
output "read_client_id" { value = google_service_account.client_read.email }
output "write_client_id" { value = google_service_account.client_write.email }
output "admin_client_id" { value = google_service_account.client_admin.email }

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

# Workers
output "processor_id" { value = google_cloudfunctions2_function.processor.id }
output "relay_id" { value = google_cloudfunctions2_function.relay.id }
output "archiver_id" { value = google_cloudfunctions2_function.archiver.id }

# Schedules
output "relay_job_name" { value = google_cloud_scheduler_job.relay.id }
output "archiver_job_name" { value = google_cloud_scheduler_job.archiver.id }

# Audit
output "audit_bucket" { value = google_storage_bucket.audit.name }
output "audit_prefix" { value = "events" }

# Network
output "vpc_id" { value = google_compute_network.vpc.id }
output "ingress_subnet_id" { value = google_compute_subnetwork.ingress.id }
output "private_subnet_id" { value = google_compute_subnetwork.private.id }

# IAM
output "api_service_account" { value = google_service_account.api.email }
output "processor_service_account" { value = google_service_account.processor.email }
output "relay_service_account" { value = google_service_account.relay.email }
output "archiver_service_account" { value = google_service_account.archiver.email }
output "scheduler_service_account" { value = google_service_account.scheduler.email }

# KMS
output "kms_keyring_id" { value = google_kms_key_ring.ring.id }
output "kms_database_key_id" { value = google_kms_crypto_key.database.id }
output "kms_messaging_key_id" { value = google_kms_crypto_key.messaging.id }
output "kms_projection_key_id" { value = google_kms_crypto_key.projection.id }
output "kms_audit_key_id" { value = google_kms_crypto_key.audit.id }

# Logs
output "logs_api" { value = google_logging_project_bucket_config.main.bucket_id }
output "logs_processor" { value = google_logging_project_bucket_config.main.bucket_id }
output "logs_relay" { value = google_logging_project_bucket_config.main.bucket_id }
output "logs_archiver" { value = google_logging_project_bucket_config.main.bucket_id }
