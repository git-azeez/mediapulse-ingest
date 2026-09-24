resource "google_service_account" "api" {
  account_id   = "${var.prefix}-api-sa"
  display_name = "MediaPulse Ingest Cloud Run API Service Account"
}

resource "google_service_account" "processor" {
  account_id   = "${var.prefix}-processor-sa"
  display_name = "MediaPulse Ingest Event Processor Function Service Account"
}

resource "google_service_account" "relay" {
  account_id   = "${var.prefix}-relay-sa"
  display_name = "MediaPulse Ingest Outbox Relay Function Service Account"
}

resource "google_service_account" "archiver" {
  account_id   = "${var.prefix}-archiver-sa"
  display_name = "MediaPulse Ingest Audit Archiver Function Service Account"
}

resource "google_service_account" "scheduler" {
  account_id   = "${var.prefix}-scheduler-sa"
  display_name = "MediaPulse Ingest Cloud Scheduler Invoker Service Account"
}

resource "google_service_account" "pubsub_invoker" {
  account_id   = "${var.prefix}-pubsub-invoker-sa"
  display_name = "MediaPulse Ingest Pub/Sub Push Invoker Service Account"
}

resource "google_project_iam_member" "api_cloudsql_client" {
  project = var.gcp_project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_datastore_viewer" {
  project = var.gcp_project_id
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_db_secret_accessor" {
  secret_id = google_secret_manager_secret.db_credentials.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_pubsub_topic_iam_member" "api_publish_events" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.api.email}"
}

resource "google_pubsub_subscription_iam_member" "processor_consume_events" {
  subscription = google_pubsub_subscription.processor_push.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "processor_datastore_user" {
  project = var.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "relay_cloudsql_client" {
  project = var.gcp_project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.relay.email}"
}

resource "google_pubsub_topic_iam_member" "relay_publish_events" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.relay.email}"
}

resource "google_project_iam_member" "archiver_cloudsql_client" {
  project = var.gcp_project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.archiver.email}"
}

resource "google_storage_bucket_iam_member" "archiver_write_audit" {
  bucket = google_storage_bucket.audit.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.archiver.email}"
}
