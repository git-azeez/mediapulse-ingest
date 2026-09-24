resource "google_cloudfunctions2_function" "processor" {
  name        = "${var.prefix}-processor"
  location    = var.gcp_region
  description = "Media Processor Cloud Function"

  build_config {
    runtime     = "nodejs18"
    entry_point = "processMedia"
    source {
      storage_source {
        bucket = google_storage_bucket.audit.name
        object = "processor-source.zip"
      }
    }
  }

  service_config {
    max_instance_count = 10
    available_memory   = "256M"
    timeout_seconds    = 60
    service_account_email = google_service_account.worker.email
    vpc_connector      = google_vpc_access_connector.connector.id

    environment_variables = {
      GCP_PROJECT_ID      = var.gcp_project_id
      FIRESTORE_COLLECTION = "media_projections"
      REDIS_URL           = "redis://${google_redis_instance.cache.host}:${google_redis_instance.cache.port}"
    }
  }

  event_trigger {
    trigger_region = var.gcp_region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.events.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }
}

resource "google_cloudfunctions2_function" "relay" {
  name        = "${var.prefix}-relay"
  location    = var.gcp_region
  description = "Outbox Relay Cloud Function"

  build_config {
    runtime     = "nodejs18"
    entry_point = "relayOutbox"
    source {
      storage_source {
        bucket = google_storage_bucket.audit.name
        object = "relay-source.zip"
      }
    }
  }

  service_config {
    max_instance_count    = 2
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = google_service_account.worker.email
    vpc_connector         = google_vpc_access_connector.connector.id

    environment_variables = {
      DATABASE_URL    = "postgresql://${var.db_username}:${var.db_password}@${google_sql_database_instance.postgres.private_ip_address}:5432/${var.db_name}?sslmode=disable"
      PUBSUB_TOPIC_ID = google_pubsub_topic.events.id
    }
  }
}

resource "google_cloudfunctions2_function" "archiver" {
  name        = "${var.prefix}-archiver"
  location    = var.gcp_region
  description = "Audit Archiver Cloud Function"

  build_config {
    runtime     = "nodejs18"
    entry_point = "archiveAudit"
    source {
      storage_source {
        bucket = google_storage_bucket.audit.name
        object = "archiver-source.zip"
      }
    }
  }

  service_config {
    max_instance_count    = 2
    available_memory      = "256M"
    timeout_seconds       = 120
    service_account_email = google_service_account.worker.email
    vpc_connector         = google_vpc_access_connector.connector.id

    environment_variables = {
      DATABASE_URL = "postgresql://${var.db_username}:${var.db_password}@${google_sql_database_instance.postgres.private_ip_address}:5432/${var.db_name}?sslmode=disable"
      GCS_BUCKET   = google_storage_bucket.audit.name
      GCS_PREFIX   = "events/"
    }
  }
}
