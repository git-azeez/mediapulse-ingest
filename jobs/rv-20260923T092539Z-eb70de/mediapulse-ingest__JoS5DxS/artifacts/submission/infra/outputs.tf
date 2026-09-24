output "load_balancer_ip" {
  description = "Public IP address of global external HTTP load balancer."
  value       = google_compute_global_forwarding_rule.forwarding_rule.ip_address
}

output "manifest" {
  description = "Machine-readable MediaPulse Ingest deployment inventory."
  sensitive   = true

  value = {
    schema_version = 1
    prefix         = var.prefix
    region         = var.gcp_region
    gcp_project_id = var.gcp_project_id

    load_balancer = {
      ip_address  = google_compute_global_forwarding_rule.forwarding_rule.ip_address
      url         = "http://${google_compute_global_forwarding_rule.forwarding_rule.ip_address}"
      connect_url = "http://${google_compute_global_forwarding_rule.forwarding_rule.ip_address}"
    }

    cloud_run = {
      service_name = google_cloud_run_v2_service.api.name
      url          = google_cloud_run_v2_service.api.uri
      location     = google_cloud_run_v2_service.api.location
    }

    database = {
      instance_name   = google_sql_database_instance.postgres.name
      db_name         = var.db_name
      connection_name = google_sql_database_instance.postgres.connection_name
    }

    pubsub = {
      topic_id             = google_pubsub_topic.events.id
      subscription_id      = google_pubsub_subscription.processor.id
      dead_letter_topic_id = google_pubsub_topic.dead_letter.id
    }

    firestore = {
      database_id     = google_firestore_database.database.name
      collection_name = "media_projections"
    }

    memorystore = {
      instance_id = google_redis_instance.cache.id
      host        = google_redis_instance.cache.host
      port        = google_redis_instance.cache.port
    }

    workers = {
      processor_name = google_cloudfunctions2_function.processor.name
      relay_name     = google_cloudfunctions2_function.relay.name
      archiver_name  = google_cloudfunctions2_function.archiver.name
    }

    schedules = {
      relay_job_name    = google_cloud_scheduler_job.relay.name
      archiver_job_name = google_cloud_scheduler_job.archiver.name
    }

    audit = {
      bucket_name = google_storage_bucket.audit.name
      prefix      = "events/"
    }

    network = {
      vpc_name    = google_compute_network.vpc.name
      subnet_name = google_compute_subnetwork.private.name
    }

    iam = {
      api_sa_email    = google_service_account.api.email
      worker_sa_email = google_service_account.worker.email
    }

    kms = {
      key_ring_id     = google_kms_key_ring.keyring.id
      crypto_key_name = google_kms_crypto_key.crypto_key.name
    }
  }
}
