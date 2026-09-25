# Cloud Functions (2nd gen) - processor, relay, archiver workers

# Processor worker - HTTP function triggered by the Pub/Sub push subscription
resource "google_cloudfunctions2_function" "processor" {
  name        = "${local.prefix}-processor"
  project     = local.project_id
  location    = local.region
  description = "MediaPulse projector worker consuming Pub/Sub push events"
  labels      = local.common_labels

  build_config {
    runtime     = "python311"
    entry_point = "handler"
    source {
      storage_source {
        bucket = google_storage_bucket.audit.name
        object = "source/processor-placeholder.zip"
      }
    }
  }

  service_config {
    service_account_email      = google_service_account.processor.email
    max_instance_count         = 10
    min_instance_count         = 0
    available_memory           = "512Mi"
    timeout_seconds            = 120
    ingress_settings           = "ALLOW_ALL"

    environment_variables = {
      FIRESTORE_DATABASE   = google_firestore_database.main.name
      DATASTORE_NAMESPACE   = local.datastore_namespace
      GOOGLE_CLOUD_PROJECT  = local.project_id
      PUBSUB_TOPIC          = google_pubsub_topic.main.name
      DLQ_TOPIC             = google_pubsub_topic.dlq.name
    }
  }
}

# Outbox relay worker - HTTP function invoked by Cloud Scheduler (1m)
resource "google_cloudfunctions2_function" "relay" {
  name        = "${local.prefix}-relay"
  project     = local.project_id
  location    = local.region
  description = "MediaPulse outbox relay polling Cloud SQL and publishing to Pub/Sub"
  labels      = local.common_labels

  build_config {
    runtime     = "python311"
    entry_point = "handler"
    source {
      storage_source {
        bucket = google_storage_bucket.audit.name
        object = "source/relay-placeholder.zip"
      }
    }
  }

  service_config {
    service_account_email      = google_service_account.relay.email
    max_instance_count         = 5
    min_instance_count         = 0
    available_memory           = "512Mi"
    timeout_seconds            = 300
    ingress_settings           = "ALLOW_ALL"

    environment_variables = {
      DATABASE_URL         = local.database_url
      PUBSUB_TOPIC         = google_pubsub_topic.main.name
      GOOGLE_CLOUD_PROJECT = local.project_id
    }
  }
}

# Audit archiver worker - HTTP function invoked by Cloud Scheduler (5m)
resource "google_cloudfunctions2_function" "archiver" {
  name        = "${local.prefix}-archiver"
  project     = local.project_id
  location    = local.region
  description = "MediaPulse audit archiver writing NDJSON batches to GCS and BigQuery"
  labels      = local.common_labels

  build_config {
    runtime     = "python311"
    entry_point = "handler"
    source {
      storage_source {
        bucket = google_storage_bucket.audit.name
        object = "source/archiver-placeholder.zip"
      }
    }
  }

  service_config {
    service_account_email      = google_service_account.archiver.email
    max_instance_count         = 5
    min_instance_count         = 0
    available_memory           = "512Mi"
    timeout_seconds            = 300
    ingress_settings           = "ALLOW_ALL"

    environment_variables = {
      DATABASE_URL         = local.database_url
      GCS_BUCKET           = google_storage_bucket.audit.name
      BIGQUERY_DATASET     = google_bigquery_dataset.audit.dataset_id
      GOOGLE_CLOUD_PROJECT = local.project_id
    }
  }
}

# IAM: allow Pub/Sub push (via processor SA) and Scheduler (via scheduler SA) to invoke the functions
resource "google_cloudfunctions2_function_iam_member" "processor_invoker_proc" {
  project        = local.project_id
  location       = local.region
  cloud_function = google_cloudfunctions2_function.processor.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_cloudfunctions2_function_iam_member" "relay_invoker_sched" {
  project        = local.project_id
  location       = local.region
  cloud_function = google_cloudfunctions2_function.relay.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloudfunctions2_function_iam_member" "archiver_invoker_sched" {
  project        = local.project_id
  location       = local.region
  cloud_function = google_cloudfunctions2_function.archiver.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.scheduler.email}"
}
