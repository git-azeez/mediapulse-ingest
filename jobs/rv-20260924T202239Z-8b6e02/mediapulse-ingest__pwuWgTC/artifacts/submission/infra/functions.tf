# ---- Processor worker (triggered by Pub/Sub push subscription) ----
resource "google_cloudfunctions2_function" "processor" {
  name        = local.processor_fn_name
  location    = var.region
  description = "MediaPulse projector: consumes media events, updates Firestore, invalidates Datastore cache"
  labels      = local.common_labels

  build_config {
    runtime     = "python311"
    entry_point = "handler"
  }

  service_config {
    service_account_email       = google_service_account.processor.email
    max_instance_count           = 10
    ingress_settings             = "ALLOW_ALL"
    environment_variables = {
      FIRESTORE_DATABASE    = google_firestore_database.main.name
      DATASTORE_NAMESPACE   = local.datastore_namespace
      GOOGLE_CLOUD_PROJECT  = var.project_id
      PROCESSOR_IMAGE       = var.processor_image
    }
  }
}

# ---- Outbox relay worker (invoked on 1-minute schedule) ----
resource "google_cloudfunctions2_function" "relay" {
  name        = local.relay_fn_name
  location    = var.region
  description = "MediaPulse outbox relay: polls Cloud SQL outbox and publishes to Pub/Sub"
  labels      = local.common_labels

  build_config {
    runtime     = "python311"
    entry_point = "handler"
  }

  service_config {
    service_account_email = google_service_account.relay.email
    max_instance_count     = 5
    ingress_settings       = "ALLOW_ALL"
    environment_variables = {
      DATABASE_URL        = local.database_url
      PUBSUB_TOPIC        = google_pubsub_topic.main.name
      GOOGLE_CLOUD_PROJECT = var.project_id
      RELAY_IMAGE         = var.relay_image
    }
  }
}

# ---- Audit archiver worker (invoked every 5 minutes) ----
resource "google_cloudfunctions2_function" "archiver" {
  name        = local.archiver_fn_name
  location    = var.region
  description = "MediaPulse audit archiver: writes NDJSON audit batches to GCS and BigQuery"
  labels      = local.common_labels

  build_config {
    runtime     = "python311"
    entry_point = "handler"
  }

  service_config {
    service_account_email = google_service_account.archiver.email
    max_instance_count     = 5
    ingress_settings       = "ALLOW_ALL"
    environment_variables = {
      DATABASE_URL        = local.database_url
      GCS_BUCKET           = google_storage_bucket.audit.name
      GOOGLE_CLOUD_PROJECT = var.project_id
      ARCHIVER_IMAGE       = var.archiver_image
    }
  }
}
