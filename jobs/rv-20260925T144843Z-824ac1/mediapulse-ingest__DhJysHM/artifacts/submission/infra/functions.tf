locals {
  datastore_namespace = "${local.prefix}-cache"
}

# Processor worker: triggered by Pub/Sub push subscription (push_endpoint points here)
resource "google_cloudfunctions2_function" "processor" {
  name        = "${local.prefix}-processor"
  project     = local.project
  location    = local.region
  description = "MediaPulse projector worker (pubsub push)"
  labels      = local.labels
  kms_key_name = google_kms_crypto_key.projection.id

  build_config {
    runtime     = "go122"
    entry_point = "Processor"
    source {
      storage_source {
        bucket = google_storage_bucket.audit.name
        object = "source-placeholder"
      }
    }
  }

  service_config {
    service_account_email          = google_service_account.processor.email
    ingress_settings                = "ALLOW_INTERNAL_ONLY"
    max_instance_count             = 10
    min_instance_count             = 0
    available_memory                = "512Mi"
    timeout_seconds                 = 60

    environment_variables = {
      FIRESTORE_DATABASE   = google_firestore_database.main.name
      DATASTORE_NAMESPACE  = local.datastore_namespace
      GOOGLE_CLOUD_PROJECT = local.project
      PUBSUB_TOPIC         = google_pubsub_topic.main.name
    }
  }
}

# Outbox relay worker: triggered by Cloud Scheduler (1m)
resource "google_cloudfunctions2_function" "relay" {
  name        = "${local.prefix}-relay"
  project     = local.project
  location    = local.region
  description = "MediaPulse outbox relay worker (scheduler)"
  labels      = local.labels

  build_config {
    runtime     = "go122"
    entry_point = "Relay"
    source {
      storage_source {
        bucket = google_storage_bucket.audit.name
        object = "source-placeholder"
      }
    }
  }

  service_config {
    service_account_email          = google_service_account.relay.email
    ingress_settings                = "ALLOW_INTERNAL_ONLY"
    max_instance_count             = 10
    min_instance_count             = 0
    available_memory                = "512Mi"
    timeout_seconds                 = 60

    environment_variables = {
      DATABASE_URL         = local.db_url
      PUBSUB_TOPIC         = google_pubsub_topic.main.name
      GOOGLE_CLOUD_PROJECT = local.project
    }
  }
}

# Audit archiver worker: triggered by Cloud Scheduler (5m)
resource "google_cloudfunctions2_function" "archiver" {
  name        = "${local.prefix}-archiver"
  project     = local.project
  location    = local.region
  description = "MediaPulse audit archiver worker (scheduler)"
  labels      = local.labels

  build_config {
    runtime     = "go122"
    entry_point = "Archiver"
    source {
      storage_source {
        bucket = google_storage_bucket.audit.name
        object = "source-placeholder"
      }
    }
  }

  service_config {
    service_account_email          = google_service_account.archiver.email
    ingress_settings                = "ALLOW_INTERNAL_ONLY"
    max_instance_count             = 10
    min_instance_count             = 0
    available_memory                = "512Mi"
    timeout_seconds                 = 120

    environment_variables = {
      DATABASE_URL         = local.db_url
      GCS_BUCKET           = google_storage_bucket.audit.name
      GOOGLE_CLOUD_PROJECT = local.project
    }
  }
}

# Allow scheduler service account to invoke relay and archiver functions
resource "google_cloudfunctions2_function_iam_member" "relay_invoker" {
  project        = local.project
  location       = local.region
  cloud_function = google_cloudfunctions2_function.relay.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloudfunctions2_function_iam_member" "archiver_invoker" {
  project        = local.project
  location       = local.region
  cloud_function = google_cloudfunctions2_function.archiver.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloudfunctions2_function_iam_member" "processor_invoker" {
  project        = local.project
  location       = local.region
  cloud_function = google_cloudfunctions2_function.processor.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.processor.email}"
}
