output "load_balancer_url" {
  description = "External HTTP Application Load Balancer entry point."
  value       = "http://${google_compute_global_address.api_ip.address}"
}

output "cloud_run_service_name" {
  value = google_cloud_run_v2_service.api.name
}

output "pubsub_topic_id" {
  value = google_pubsub_topic.events.id
}

output "manifest" {
  description = "Machine-readable MediaPulse Ingest GCP deployment manifest written to manifest.json by deploy.sh."
  sensitive   = true

  value = {
    schema_version   = 1
    prefix           = var.prefix
    project_id       = var.gcp_project_id
    region           = var.gcp_region
    gcp_endpoint_url = var.gcp_endpoint_url

    approved_images = {
      api       = { reference = var.api_image, image_id = var.api_image_id }
      processor = { reference = var.processor_image, image_id = var.processor_image_id }
      relay     = { reference = var.relay_image, image_id = var.relay_image_id }
      archiver  = { reference = var.archiver_image, image_id = var.archiver_image_id }
    }

    load_balancer = {
      ip_address         = google_compute_global_address.api_ip.address
      url                = "http://${google_compute_global_address.api_ip.address}"
      connect_url        = coalesce(google_cloud_run_v2_service.api.uri, "${var.gcp_endpoint_url}/run/${google_cloud_run_v2_service.api.name}")
      forwarding_rule_id = google_compute_global_forwarding_rule.http.id
      backend_service_id = google_compute_backend_service.api.id
      serverless_neg_id  = google_compute_region_network_endpoint_group.api_serverless_neg.id
    }

    cloud_run = {
      service_id         = google_cloud_run_v2_service.api.id
      service_name       = google_cloud_run_v2_service.api.name
      service_uri        = google_cloud_run_v2_service.api.uri
      min_instance_count = local.api_min_instances
      max_instance_count = local.api_max_instances
    }

    database = {
      instance_name = google_sql_database_instance.events.name
      private_ip    = local.database_host
      port          = local.database_port
      name          = google_sql_database.mediapulse.name
      secret_id     = google_secret_manager_secret.db_credentials.secret_id
    }

    messaging = {
      topic_id              = google_pubsub_topic.events.id
      topic_name            = google_pubsub_topic.events.name
      subscription_id       = google_pubsub_subscription.processor_push.id
      dlq_topic_id          = google_pubsub_topic.dead_letters.id
      dlq_subscription_id   = google_pubsub_subscription.dead_letters.id
      max_delivery_attempts = 5
      rebuild_tasks_queue   = google_cloud_tasks_queue.projection_rebuild.name
    }

    projections = {
      firestore_database = google_firestore_database.projections.name
      collection         = "media_timeline"
      bigquery_dataset   = google_bigquery_dataset.audit_analytics.dataset_id
    }

    cache = {
      engine              = "cloud-datastore"
      datastore_namespace = "${var.prefix}-cache"
      emulator_host       = local.datastore_emulator_host
    }

    auth = {
      tenant_id                  = google_identity_platform_tenant.mediapulse.name
      resource_server_identifier = local.auth_resource_server
      issuer                     = local.auth_issuer
      jwks_url                   = local.auth_jwks_url
      read_client_email          = google_service_account.client_read.email
      write_client_email         = google_service_account.client_write.email
      admin_client_email         = google_service_account.client_admin.email
    }

    workers = {
      processor_id = google_cloudfunctions2_function.processor.id
      relay_id     = google_cloudfunctions2_function.relay.id
      archiver_id  = google_cloudfunctions2_function.archiver.id
    }

    schedules = {
      relay_job_name    = google_cloud_scheduler_job.relay.name
      archiver_job_name = google_cloud_scheduler_job.archiver.name
    }

    audit = {
      bucket = google_storage_bucket.audit.name
      prefix = "events/"
    }

    network = {
      vpc_id            = google_compute_network.ingest.id
      ingress_subnet_id = google_compute_subnetwork.ingress.id
      private_subnet_id = google_compute_subnetwork.private.id
    }

    iam = {
      api_service_account       = google_service_account.api.email
      processor_service_account = google_service_account.processor.email
      relay_service_account     = google_service_account.relay.email
      archiver_service_account  = google_service_account.archiver.email
      scheduler_service_account = google_service_account.scheduler.email
    }

    kms = {
      keyring_id        = google_kms_key_ring.mediapulse.id
      database_key_id   = google_kms_crypto_key.database.id
      messaging_key_id  = google_kms_crypto_key.messaging.id
      projection_key_id = google_kms_crypto_key.projection.id
      audit_key_id      = google_kms_crypto_key.audit.id
    }

    logs = {
      api       = google_logging_project_bucket_config.api.bucket_id
      processor = google_logging_project_bucket_config.processor.bucket_id
      relay     = google_logging_project_bucket_config.relay.bucket_id
      archiver  = google_logging_project_bucket_config.archiver.bucket_id
    }
  }
}
