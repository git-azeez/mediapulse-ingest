locals {
}

resource "google_service_account" "api" {
  account_id   = "${local.prefix}-api"
  display_name = "MediaPulse API Cloud Run"
  project      = local.project
}

resource "google_service_account" "processor" {
  account_id   = "${local.prefix}-processor"
  display_name = "MediaPulse Processor Function"
  project      = local.project
}

resource "google_service_account" "relay" {
  account_id   = "${local.prefix}-relay"
  display_name = "MediaPulse Outbox Relay Function"
  project      = local.project
}

resource "google_service_account" "archiver" {
  account_id   = "${local.prefix}-archiver"
  display_name = "MediaPulse Audit Archiver Function"
  project      = local.project
}

resource "google_service_account" "scheduler" {
  account_id   = "${local.prefix}-scheduler"
  display_name = "MediaPulse Scheduler Invoker"
  project      = local.project
}

# Project-level role bindings
resource "google_project_iam_member" "api_cloudsql_client" {
  project = local.project
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_datastore_viewer" {
  project = local.project
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_pubsub_publisher" {
  project = local.project
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "processor_datastore_user" {
  project = local.project
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "relay_cloudsql_client" {
  project = local.project
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.relay.email}"
}

resource "google_project_iam_member" "relay_pubsub_publisher" {
  project = local.project
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.relay.email}"
}

resource "google_project_iam_member" "archiver_cloudsql_client" {
  project = local.project
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.archiver.email}"
}

resource "google_project_iam_member" "api_kms" {
  project = local.project
  role    = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "relay_kms" {
  project = local.project
  role    = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member  = "serviceAccount:${google_service_account.relay.email}"
}

resource "google_project_iam_member" "archiver_kms" {
  project = local.project
  role    = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member  = "serviceAccount:${google_service_account.archiver.email}"
}

resource "google_project_iam_member" "processor_kms" {
  project = local.project
  role    = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member  = "serviceAccount:${google_service_account.processor.email}"
}
